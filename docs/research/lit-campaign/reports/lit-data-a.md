# lit-data-a: data, pretraining and synthetic plans, field and state of the art (L8, angle a)

Worker lit-data-a, read-only. Final version 2026-11-14 about 01:15 by the machine clock (wrapped up early on the orchestrator's new deadline), updated each round (see the
reading log `lit-data-a-log.md`, one line per source). Scope: L8 in `docs/research/lit-campaign/scopes.md`. Angle a:
floor-plan and technical-drawing work, 2025-2026 on purpose, citation walks forward from ResPlan, ArchCAD-400K,
CubiCasa5K and the 2026 synthetic-plan paper. Extends, does not repeat: `stoa-data.md`, notes A, B, C, and
`stoa-hardimg-notes/06-augmentation.md`. Sideways transfers are angle b's job; the ones below are only those I met on
the way and opened.

Marks: **[V]** = I read it on the page named (verbatim, or the full text I extracted). **[S]** = part of the page
reached me only as a model summary of a truncated fetch; it is marked and not relied on for a ranking. **[R]** =
reported by the authors. All dates read: 2026-11-14 unless stated. Hours are my estimates, marked "est.".

## 0. The answer in six lines

1. Nothing we found is both commercial-safe and a real-image set with our fixture classes. The best commercial-safe
   material is **generated**: an MIT procedural generator that draws toilet, sink, shower, bathtub and stove boxes in four
   styles with a registered degradation stack (fpgen, 2026), plus layouts from ResPlan (2025; licence text CC BY 4.0, repo metadata NC-SA, unresolved).
2. The only study that measured "real plus synthetic" against "real only" on **floor plans with thousands of real
   images** found no significant gain: wall F1 on CubiCasa5K test +1.2 (rooms-first model) and +0.4 (wall-first model)
   against a bootstrap half-width of 1.3 to 1.7 points (arXiv 2608.25608, Table 4 area, [V]). Expect synthetic plans to
   help rare classes and robustness, not the headline score.
3. Where real data is **tiny** the gap is enormous: synthetic-only detectors on real engineering drawings collapse (DETR,
   P&ID: 90.5 mAP on synthetic test, 33.8 on a two-sheet real set, 4.0 on the 12-sheet OPEN100 set, [V]; Relationformer
   symbols mAP 26.7 synthetic-only against 73.5 with 60 real sheets mixed in, [V]). Never train synthetic-only.
4. The one controlled study of what breaks on real scans (Carrara, Nousias, Borrmann, Automation in Construction 191,
   2026, abstract [V]; full text blocked, data released on Zenodo as CubiCasa5k-ScanShift, CC BY-NC 4.0) says the loss comes from changed **depiction inside the object region**
   (stroke width, blur, boundary ambiguity), not from paper texture. So randomise line weight and blur, not backgrounds.
5. Self-supervised pretraining on line drawings: **no 2025-2026 paper measures it for detection on floor plans**. The
   nearest results are a frozen DINOv3 plus DPT head contrastive model on floor plans that includes CubiCasa5K in its
   training (arXiv 2609.12723, leak, no door or window evaluation) and a line-drawing pretraining paper on natural
   images only (arXiv 2508.06696). The practical pretraining is **DINOv2 initialisation inside RF-DETR** (Apache-2.0
   code and weights): +3.5 APS over the CAE backbone on COCO, and the authors' claim that it "significantly improves
   detection accuracy on small datasets".
6. The best commercial-safe set we could assemble in a night: our own dev-split labels (allowed by record 0003) as the
   backbone of training, with fpgen renders as a supplement for bathtub, sauna stove and rare fixtures, rendered at 855 px
   with our label vocabulary and the Carrara-style depiction jitter. Section 4 has the recipe and the measurements to
   run before trusting it.

## 1. Top 5 (floor-plan work and transfers in one list)

Rank is by evidence we can use tonight, then licence, then fit to the JSON fields.

### 1. fpgen, the procedural plan generator in `fpvec-lab` (arXiv 2608.25608, Aug 2026), verdict: **try**, as a supplement
- What: generates stylised plan rasters with pixel-exact vector truth. Layout from a room-programme tree, wall graph
  with thickness classes, doors and windows with swing symbols, a fixture rule solver (toilet only in bath or WC, stove
  and sink in kitchens, collision and door-swing clearance), four render styles (clean CAD, marketing, brochure,
  hand-drawn), printed labels from a vocabulary that includes "WC", a scale bar and dimension chains, and a degradation
  stack of 19 whitelisted operations (Augraphy-based blur, ink bleed, bleed-through, low ink, photocopy, shadows, JPEG,
  down-up scaling, tiled watermark, vignette) sampled none 0.30, light 0.30, medium 0.25, heavy 0.15, with a registration
  test that keeps ground truth within 1.5 px. [V: paper Appendix B read in full; README, `symbols.py`, `scene.py`,
  `pipeline.py`, `degrade.py` read through `gh api`.]
- Code: https://github.com/Cyprinus12138/fpvec-lab, **MIT** (LICENSE file read; spdx MIT via `gh api`, pushed 2026-10-21).
  Depends on skia-python (BSD-3-Clause, `gh api`), shapely, scipy, OpenCV, scikit-image and Augraphy (MIT). Weights: none
  released that I could find (the paper states code, benchmark and corrected annotations only). Data licence:
  generated plans are ours; only fitted aggregate statistics ship, no listing content (README "Data licensing", [V]).
- Install facts [V, `pyproject.toml`, `requirements.txt`, `fpgen/` tree through `gh api`, 2026-11-14]: the `fpgen` extra is only `skia-python`; core deps numpy, shapely, scipy, scikit-image, opencv-headless, pillow (all permissive). Augraphy is **not** in either list but `degrade.py` imports it lazily inside each Augraphy op, so a missing install fails at the first degraded sample; install it separately. The `skv4` extra pulls cairosvg (LGPL-3.0 family, ours would use it unmodified as a library only if at all) and is not needed for fpgen. No `fitz`, PyMuPDF or ultralytics import in the 22 fpgen files I grepped, so nothing AGPL from record 0006's out-list. Pinned set: Python 3.11, numpy 2.4.6.
- Fixture boxes: `scene.py` serialises fixtures with `bbox` per item and `pipeline.py` writes them to the sample's
  `scene.json` and `gt.json`; the glyph table has toilet, shower, bathtub, stove and sink as named glyphs [V]. The
  paper's training only uses walls, openings and rooms, so **fixture boxes were never used or evaluated by the authors**:
  we would be the first to train on them, and the glyph shapes are Singapore-listing-fitted style (unit statistics fitted to listing titles from a Singapore property site, paper Appendix B), not Finnish.
- Measured effect on real plans: cc5k vs cc5k+synth (3,327 synthetic plans mixed 1:1 with the 3,328 CubiCasa5K training
  plans from a 10,000-plan pool): r2s-style model wall F1 0.769 to 0.781, openings 0.840 to 0.848; wall-first model wall
  F1 0.747 to 0.751, openings 0.341 to 0.367; per-system bootstrap half-width on wall F1 0.013 to 0.017, so **inside the
  noise** [V, same tables]. The paper has no per-class or fixture result, because it never trained on fixtures.
- Input size and GPU: not applicable (generator is CPU, skia); the paper's training used 500 epochs, hardware not stated
  for training in the parts I read.
- Hours to a first number on our data (est.): 3 to 4 h of adapter work (class map to our eight classes, Finnish label
  vocabulary and sauna-stove glyph, render at 855 px longest side, COCO export of fixture boxes), then generation of 5k
  plans is CPU minutes to an hour (est.), then one detector run. Fills `elements` (window, door, toilet, sink, shower,
  bathtub, sauna stove), `rooms` labels (WC, bath), `scale` (scale bar value), `plans` (always 1: we would have to
  compose multi-plan sheets ourselves).
- Glyphs [V, `symbols.py`]: toilet is a tank rectangle plus an ellipse, shower a square with two diagonals and a circle,
  bathtub a rectangle with an inner rounded rectangle and a drain circle, sink a rectangle with an inner rounded
  rectangle and a tap, "stove" a four-burner hob in the kitchen; there is no sauna stove and no text "sauna" in the
  generator (`grep` of the package found none).
- Scale and exports [V, `render.py`, `pipeline.py`, `scene.py`]: each plan is rendered with a long side drawn uniformly
  from 900 to 1600 px and then fitted into a 1024 px frame (`FRAME = 1024.0`); `gt.json` carries `fixtures` (kind, quad,
  axis-aligned `bbox` in image pixels, room label), `texts` (room labels, areas, dimensions with `bbox`), walls and
  rooms; `manifest.jsonl` records `mm_per_px`. So a plan of 10 to 14 m is about 70 to 100 px per metre and a 0.4 by 0.7 m
  toilet is roughly 28 by 50 px, **larger than our 5 to 20 px symbols**: a down-scaling step to 0.3 to 0.6 of that
  (the whitelist's `down_up` op scales by U(0.55, 0.9) and back, read in `degrade.py`, so it does not reach 0.3 to 0.6) has to be added for the small-symbol regime.
- What breaks on our images: Singapore symbol set and room programme (no sauna, no Finnish labels MH, OH, KH, PH, K);
  Manhattan walls only plus a chamfer option; symbols drawn in vector skia strokes with clean antialiasing, so 5 to 20 px
  symbols are cleaner than a real downscaled scan; rotation augmentation is limited to similarity within 3 degrees (we
  need exact 90 and 180 multiples, which is trivial to add after rendering); no photographed sheets.
- Leakage flag: generator itself none. The authors' **checkpoints** are trained on CubiCasa5K (cc5k and mix arms): none
  are released, and any we would train ourselves from it would not use CubiCasa5K.

### 2. DINOv2 initialisation inside RF-DETR (arXiv 2511.09554, v2 Feb 2026), verdict: **try**
- What: the real-time detector's backbone is a DINOv2 ViT; the authors state that DINOv2 initialisation "significantly
  improves detection accuracy on small datasets" [V, text of the full paper via a headless browser]. Their only
  backbone ablation (Table 6, COCO, LW-DETR-M, Objects-365 pretrained 60 epochs): CAEv2 ViT-S/16 AP 52.3, APS 32.3;
  DINOv2 ViT-S/14 AP 54.3, APS 35.8; SigLIPv2 ViT-B/32 AP 50.4, APS 28.0; SAM2 Hiera-S AP 53.6, APS 33.3 [V]. Image
  resolutions in its search grid run 320 to 960 px. No document, line-drawing or floor-plan result in the paper.
- Corroboration for self-supervised backbones on small sets, not drawings: DINO-YOLO (arXiv 2510.25140, abstract [V]) adds DINOv3 features to YOLOv12 and reports gains on datasets under 10k images (648-image tunnel cracks +12.4%, 1k-image PPE +13.7%, KITTI +88.6% as stated by the authors); it builds on YOLO (AGPL, out) and DINOv3 (custom licence, out), so it is evidence only, not a candidate.
- Code licence: **Apache-2.0** (LICENSE and README read; spdx via `gh api`, pushed 2026-11-13). Weights: the README
  states Apache-2.0 for RF-DETR N, S, M, L and every Seg size, and PML 1.0 for Atto, Femto, Pico, XL and 2XL [V]; the
  Hugging Face card for `Roboflow/rf-detr-large` is `apache-2.0` and `facebook/dinov2-base` is `apache-2.0` (cards read
  through the Hub API) [V]. Training data of the base weights: COCO and Objects-365 (pseudo-labelled with SAM2), no
  CubiCasa5K. **Leakage flag: no for the released COCO checkpoints. The RF100-VL benchmark (Apache-2.0 repo, 100 datasets in seven
  categories, dataset list read from its `dataset_name_to_category.json`) has no floor-plan set by name; its ten
  "Document" sets are activity diagrams, circuit voltages, invoices and similar, so its AP numbers say little about
  drawings.**
- Input size and GPU: the README table [V] lists the Apache sizes at N 384, S 512, M 576, L 704 px, 30.5 to 33.9 M
  params, RF100-VL AP50 85.0 to 88.2 (authors' benchmark on 100 Roboflow sets, not drawings); I did not measure
  memory. The repo docs (`docs/index.md` FAQ, [V]) recommend a CUDA GPU with at least 8 GB VRAM for fine-tuning, say N and S
  fit 6 GB with a reduced batch, and accept COCO JSON or YOLO folders, so our 12 GB card is inside the documented range
  (reported by the maintainers, not measured by me). 704 px is below our 855 px median sheet, so small symbols need tiling. The paper says gradient accumulation was added "to facilitate training on consumer-grade
  GPUs" [V]. Hours to first number (est.): 2 to 3 h on the 12 GB card at 1024 px tiles if the install works; the earlier
  campaign reports already rank this family, so this row only adds the **backbone evidence** and the licence read.
- What breaks: ViT patch 14 or 16 and a 4x down-projection means a 6 px symbol covers under half a patch; this is why
  tiling at native resolution matters (see lit-detect). The pretraining is on photographs: the only test of RF-DETR on
  drawings I found is the AEC layout benchmark (arXiv 2607.18997, EC3 2026, full PDF text read [V]): 551 facade drawings
  from 10 projects, nine layout classes, 70:15:15 split, **no augmentation**, RF-DETR-M at 1344 by 800 px reaches mAP50
  0.949 and mAP50:95 0.890, against Faster R-CNN 0.930 / 0.779 and YOLOv12-M 0.871 / 0.755 (YOLOv12 is AGPL-class
  Ultralytics-family, out for us). Table 2 of that paper (re-read in the extracted text) also shows RF-DETR-M's precision 0.985 but **recall only 0.800** at confidence 0.25 against 0.924 for Faster R-CNN, 44.8 ms per image, 33.7 M parameters: it is conservative at that threshold, which for exact counting means the threshold must be tuned on dev for recall, not left at 0.25; it also shows the model run at 1344 by 800, well above its 576 px native size. So a DINOv2-initialised detector trains well from about 380 training drawings, but
  these are large layout regions (title block, section views), not 6 px symbols.
- Known limits from the repo's issue tracker [V, threads #669, #780 and #958 read in full through `gh`]: the detector
  decodes from a fixed set of learned queries, the maintainer says the pretrained count is **300** (a contributor says
  500) and that you can lower it but not raise it usefully; the instance-segmentation head is bounded at 256 objects,
  and the nano segmentation model at 100. That is far above our 20 to 100 symbols per sheet, so exact counting is not
  capped on a tile, but anyone tiling dense sheets should keep tiles under the cap. The maintainer's advice for
  small objects is to move up a size (S or M) instead of scaling the nano model's resolution, and he states the ViT
  backbone cost grows steeply with input side length (reported by the maintainer, not measured here). #958 reports
  RF-DETR-N more than halves in accuracy on a small-ball dataset at low input resolution.
- More repository facts re-read 2026-11-14 [V, `gh api`]: latest release 1.12.1 (2026-11-12); the README licence statement is unchanged (Apache-2.0 for N, S, M, L, every Seg size and Keypoint; PML 1.0 only through the `rfdetr[plus]` extra). Issue #974 (open, 2026-04) reports **training about 2x slower in v1.6.4 than v1.5.0** on 18k images at 512 px; a maintainer replied that it was not reproduced and asked for a profile, a commenter suggested the effective batch size of 16 the docs recommend and disabling augmentation (`aug_config={}`); so pin the version and time one epoch before planning hours. Issue #1599 (open, 2026-10): confidence on a 512 px tile **swings with small shifts** (for example 0.91 at 0 px, 0.49 at 11 px, back to 0.88 at 12 px) while the box stays within IoU 0.90 to 0.95; a commenter reproduced it on COCO checkpoints and attributes the period to the backbone patch grid (patch size times tile size over model resolution); localisation is stable, only the score moves. For exact counting this means a fixed threshold on tiles is brittle: use overlapping tiles with box-level merging, or small shift averaging, and check the count against a threshold sweep on dev (idea, not tested).
- Docs read 2026-11-14 [V, `docs/faq.md`, `docs/learn/train/augmentations.md` through `gh api`]: the FAQ says up to `num_queries` objects per image (300 for N, S, M, L) and that you **can raise `num_queries` and `num_select` together** (the added query rows start untrained, so fine-tune after); this is more permissive than the maintainer's remark in issue #669, so I report both and trust the docs for the mechanism, not for how well raised queries work (untested). Resolution must be divisible by patch size times windows (blocks of 32 for current detection checkpoints), so 576, 704 and 1024 are valid, 855 is not. Default training augmentation is resize/crop scale jitter plus horizontal flip 50%; custom stacks need the `augment` extra (Albumentations, which also has blur, noise, JPEG-type transforms, pixel-level ones keep boxes unchanged); the docs recommend `AUG_AGGRESSIVE` (rotation, affine, colour) for 2000+ images and say `aug_config={}` turns optional augmentation off. `grad_accum_steps` now defaults to 1 (it was 4), so the nominal batch is just `batch_size` unless set: another reason for the speed and convergence differences seen in #974.
- Dependencies [V, `pyproject.toml`]: supervision (MIT, `gh api`), PyTorch Lightning, torchmetrics, peft, and an optional
  `augment` extra that pulls `albumentations>=1.4.24,<3` (the PyPI `albumentations` 2.0.8 package is MIT; the AGPL
  fork is AlbumentationsX, a different package) and kornia. No AGPL or GPL package in the dependency lists I read.
- JSON field: elements. Verdict reason: best-supported small-object backbone with clean licences.

- Anchor for RF-DETR training time on floor plans [V, HF card of `OsamaMo/2dplan2strct`, read 2026-11-14, numbers reported by its author]: RF-DETR Medium at 576 px, best EMA checkpoint after epoch 13, 16 h on one T4 (16 GB), validation 2,964 images, mAP50 94.5, mAP50:95 82.6 on four classes (wall, room, door, window). The training set is not named, so the checkpoint is treated as possibly CubiCasa5K-trained and **not usable** (also non-commercial), but the 16 h figure says an RF-DETR-M run of this size is an overnight job on a T4-class card, and our 12 GB RTX 4070 is faster than a T4 (not measured by me). The Roboflow Universe listing of RF-DETR floor-plan models (12k-image set, a 1.8k-image set) could not be opened (JavaScript pages).

### 3. Depiction-matched augmentation and re-rendering of our own dev labels (Carrara et al. 2026 plus fpgen and Augraphy), verdict: **try**
- Evidence: Carrara, Nousias and Borrmann, "Why floor plan object detection breaks under real scans", Automation in
  Construction 191, 107193 (2026). Controlled study on CubiCasa5K with paired CAD-derived and scanned rasters of the same
  layouts, RT-DETR, three seeds, plus region-of-interest composites that separate object-region changes from background
  texture. Finding as stated in the abstract on the TUM research portal [V, abstract only; the ScienceDirect and SSRN
  full texts returned 403 and "Content Blocked" to both web-fetch and the headless browser]: degradation is "strongly
  class- and scale-dependent"; the main loss comes from changed geometry inside object regions; scanned backgrounds cost
  only a moderate decline; AP75 drops much more than AP50. They state the paired variants, scripts and **trained
  checkpoints** are released; The release is on Zenodo as
  **CubiCasa5k-ScanShift** (DOI 10.5281/zenodo.18890483, found through OpenAlex; record read through the Zenodo API
  [V]): licence **CC BY-NC 4.0**, 4.68 GB, 4,996 layouts with a clean raster, the scanned raster
 , two ROI-controlled composites and corrected SVG-derived renderings, splits 4,197 / 400 / 399. The
  OpenAlex record for the paper lists a hybrid open-access full text, but ScienceDirect refuses automated access, so
  the paper's per-class text stays unread (abstract only [V]); the repository tables above carry the numbers. **Leakage flag for the data and any checkpoints: yes, it is
  CubiCasa5K.** What it tells us for free: CubiCasa5K's own originals are the *scanned* depiction and the same layouts
  can be re-rendered clean from the SVG, so a clean-versus-scan pair per dev image can be built from files we already
  hold.
- **Numbers now read** (2026-11-14, [V] from the authors' repository https://github.com/andreacar/floorplan-detection-scan-robustness,
  `artifacts/tables/*.csv` through `gh api`; code **MIT** per README and LICENSE, trained weights and result bundles under
  a separate non-commercial `LICENSE.assets`, so `gh api` shows NOASSERTION; the README says the paper's tables mirror these
  files, I have not seen the paper itself): RT-DETR, CubiCasa5K, test split; the factorised-degradation table has `_mean` columns (a mean over something I could not identify, probably the abstract's three seeds), the other tables are single numbers, and no spread is in these files.
  Window plus door only: clean-trained AP 0.807 / AP50 0.832 / AP75 0.824; scan-trained AP 0.522 / AP50 0.751 / AP75 0.599.
  Error decomposition of 21k ground-truth boxes: clean 10.2% missed, 4.8% loose, 85.0% tight; scanned 25.5% missed,
  34.4% loose, 40.1% tight, i.e. the loss is mostly boxes found but loose, which only AP75 sees. Size at which half of
  the objects are found (IoU 0.5): **120 px of box area on clean, 909 px on scanned** (at IoU 0.85: 202 vs 6,803), so a
  scan makes the smallest findable symbol about 8 times larger in area; a 10 by 10 px symbol (100 px)
  would be below even the clean threshold, if their pixel units match ours (the tables do not state the render size, so the
  absolute areas are indicative only; the ratio is what carries over). ROI composites: clean-trained model on scan-inside-boxes AP50 0.136 against 0.474 on clean boxes with
  scanned background, scan-trained model 0.564 and 0.549: **depiction inside the object is what breaks the clean model,
  the background barely does.** Factorised degradations on the clean model (AP50 from 0.881): mild blur 0.877, medium
  0.807, strong 0.619; **thickening** mild 0.624, medium 0.253, strong 0.091; texture medium 0.691; clutter medium 0.472.
  So stroke width is the most damaging single factor, which sets the jitter ranges (dilate by 1 px must be in the
  training range; exposure to thickening is where a clean-trained detector fails). Their mitigation arms (box jitter,
  stroke erosion plus line dropout, dilate then blur then threshold) are scripts with a README only: **no result tables
  for them are in the repository**, so whether the augmentations close the gap is unmeasured here.
- Corroboration on a different task: Kuklev (arXiv 2609.24565, Sep 2026): on hatch matching a small task-trained CNN
  falls from 0.966 to 0.778 accuracy when rendering shifts from clean to scan, a frozen descriptor only from 0.857 to
  0.826; the paper's own sentence "transfer without adaptation does not work for anyone" and zero-shot synthetic-to-real
  AP 0.224 to 0.504 depending on readout [V, full page re-read through the headless browser 2026-11-14; its limitations paragraph says real document sets are small and project-imbalanced, the production drawings are proprietary, and plan geometry comes from CubiCasa5K, so any model of it is a leak].
- What to do (our recipe, not a paper's): take the dev-split labels we already have (allowed by record 0003 for
  dev-split images only), and for each training image add a randomised *re-depiction*: stroke thickening and thinning by
  morphological dilate or erode of 1 to 2 px, blur and down-up scaling to 0.5 to 1.0 of native, JPEG 40 to 92, Augraphy
  photocopy, ink bleed and low-ink-lines from the registered whitelist in fpgen `degrade.py` (all position-preserving, so
  boxes stay valid), exact rot90 and flips. This costs no new data and is directly aimed at the failure Carrara isolates.
- Hours to a first number (est.): 1 to 2 h to wire the whitelist (it is MIT and already position-safe) in front of the
  detector's loader, then one training run; the useful readout is the AP75/AP50 gap on dev with and without it.
- Augraphy as a dependency [V, `gh api` and the PyPI JSON, 2026-11-14]: MIT, last push 2025-07-20, 22 open issues, latest PyPI release 8.2.6 (uploaded 2023-12-31), requirements include numba, opencv, scikit-image, scikit-learn, scipy. So it is permissive but not actively released; numba JIT compile adds first-call latency in a dataloader, and the effects run on CPU per image (speed not measured). The morphological dilate, blur and JPEG ops in the recipe need no Augraphy at all.
- Gap in fpgen's whitelist [V, `degrade.py` read in full through `gh api`, 2026-11-14]: it has **no stroke-thickening op**. The only line-weight ops are `line_breakup` (knocks out 2 to 8% of dark pixels, thins lines), Augraphy ink bleed and low-ink lines; blur is a 3 or 5 px Gaussian kernel, JPEG quality 40 to 92, `down_up` 0.55 to 0.9, geometric scale 0.85 to 1.05. Carrara's tables rank thickening as the most damaging factor, so a dilation op (1 to 2 px, applied before blur, position-preserving) has to be added by us; it is a few lines of OpenCV and needs the same registration check.
- What breaks: all of Carrara's numbers are on CubiCasa5K renders, i.e. the same distribution as ours, so the effect on
  our phone photos and scans is unmeasured; Augraphy is documented as unmeasured for drawings (`06-augmentation.md`).

### 4. ResPlan layouts (licence disputed: CC BY 4.0 in LICENSE, NC-SA in metadata) as a layout source for the renderer in rank 1, verdict: **maybe, local training only until the licence is settled**
- What: 17,000 vector plans with walls, doors, windows, balconies, rooms and a 17-category taxonomy [R], "geometry only"
  in the GitHub pickle [V]. ModRes (arXiv 2610.17178, Oct 2026) cleans it to **8,431** valid, unique plans by removing
  plans with missing essential rooms, invalid or clustered doors, disconnected graphs and duplicates, adds three dual
  graphs and 2D renders; it states there are no furniture or fixtures and that the room taxonomy has **one "bathroom"
  and no WC** [V: full HTML page re-read through the headless browser, including the "lack of furniture" limitation and the data-availability section].
- Licences read from files: ResPlan LICENSE: data **CC BY 4.0** (`ResPlan.pkl`, `split.json`, `croissant.json`), code
  MIT; the LICENSE states the data are "derived geometric representations ... recovered by computer vision from publicly
  accessible real-estate listing renderings", that no source images are included, that spatial arrangements are facts
  with no licence asserted, and that a takedown process exists (TAKEDOWN.md) [V]. `gh api` spdx says NOASSERTION because
  the file is a dual licence. ModRes repo MIT (`gh api`; its LICENSE file is the plain MIT text of 2026 with the author's name and no separate data licence, though the repo holds `dataset/Geometry` and `dataset/Graphs`; so the data sit under an MIT notice but derive from ResPlan, whose own licence is the open question); ModRes paper licence CC BY 4.0 per its arXiv page.
- **Licence conflict, new since the earlier report:** the same repository's `croissant.json` (Kaggle version 6) declares
  the licence as **CC BY-NC-SA 4.0** (read through raw GitHub), while `LICENSE`, the README and `TAKEDOWN.md` say CC BY
  4.0; the Kaggle page text seen in a search also lists NC-SA. Two issues asking exactly this (#5, Dec 2025; #8,
  Oct 2026, "Clarification on ResPlan Commercial Licensing", opened by someone planning a commercial model) are
  **still open with no maintainer reply** [V, `gh issue view`]. ModRes inherits the question (its issue #1 asks the same,
  no reply). So "ResPlan is commercial-safe" from the earlier report must be downgraded to "licence text says CC BY 4.0,
  metadata says NC-SA, unresolved": ask the authors before shipping anything derived from it, or use it for local
  training only like the NC sets.
- Our check on the taxonomy question the earlier report left open: `resplan_utils.py` lists the category keys living,
  bedroom, bathroom, kitchen, storage, stair, door, window, wall, front_door, balcony: **no WC key**, so the WC-room
  versus bathroom question must come from the renderer's labelling, not ResPlan [V].
- Use: feed the polygons to the fpgen fixture solver (rank 1) in place of its own guillotine layouts, to get more varied
  and more realistic apartment shapes. Hours (est.): 3 to 4 h more than rank 1 (a polygon adapter). Not needed for a
  first number.
- Breaks: South Asian single-floor layouts, no sauna or Finnish programme, 6.9% near-duplicates [R], one bathroom class.
- Leakage: none (not CubiCasa5K). The 2026 ResPlan-FP benchmark of the fpvec-lab paper re-renders it under CC BY 4.0
  (HF dataset `Tristan12138/resplan-fp`, card read 2026-11-14 [V]: 16,998 plans as clean 256 px renders, wall bands and door and
  window symbols only, "No text, no fixtures"; it inherits the ResPlan licence question, since the card cites ResPlan data as
  CC BY 4.0 without mentioning the NC-SA metadata). Useless for our fixtures at 256 px. The companion `skv4` annotations
  derive from CubiCasa5K and are CC BY-NC-SA 4.0 (fpvec-lab README line 90): leak and NC. The fpvec-lab code was released
  on 2026-10-20 (commit "Release skeleton"); issue #2 asking for code, dated 2026-09-22, is stale. The ResPlan issues #5, #7, #8
  were re-read on 2026-11-14: still no maintainer reply (#5 has only a bot comment); #7 shows plans are **not** on one scale in
  the data (the asker had to rescale per plan from wall depth).

### 5. benikm91 synthetic furnished plans on Hugging Face (Oct 2026), verdict: **maybe**, only as a data-loading smoke test
- What: 1,000,000 train plus 5,000 val and 5,000 test generated plans, `(N, 256, 256)` uint8 black on white, with a
  furniture record that includes **toilet, basin, bathtub, shower, sink, hob, washer** as boxes with facing, and
  walls, doors and windows as segments [V: full dataset card read through the raw README].
- Licence: dataset card `license: cc-by-4.0` [V]; the generator repository `benikm91/synthetic-floorplans-for-transcription`
  **has no licence file** (`gh api` license is null), so we may use the released data but not copy or adapt the code.
- Why only "maybe": 256 px images with at most 20 px per metre, so a toilet is about 8 by 14 px, which is in our 5 to 20
  px range, but the plans are Manhattan grid cells on 10 cm cells with a single drawing per style, no labels or text, no
  scan degradation, no sauna. It is a clean pretraining set for "find a fixture in a thin-wall drawing", not a bridge to
  scans. Size 1M plans is more than we can use in a night; 20k to 50k plans would do.
- Hours (est.): 1 h to read the npy shards, map classes and run a pretrain on a 50k subset; the gain is unmeasured
  anywhere. **Leakage: none** (generated). Do not confuse with the Hugging Face repackage `BinniesHK-AI/...flat` below.

Not in the top 5 but ranked here for completeness: FloorPlanCAD and ArchCAD-400K pretraining (rank 6 and 7 in the table).

## 2. Full table

Columns: method or resource; field (ours or the field it transfers from); year, venue; code and licence; weights or data
and licence; training data; metric and benchmark; input size, GPU; hours to first number (est.); JSON field; leakage
flag; verdict with one reason.

| # | Resource | Field | Year, venue | Code, licence | Weights or data, licence | Training data | Metric, benchmark | Input, GPU | Hours est. | JSON field | CubiCasa5K leak | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | fpgen generator (fpvec-lab) | ours | arXiv 2608.25608, Aug 2026 | github.com/Cyprinus12138/fpvec-lab, MIT | no weights; generated data ours | procedural, stats fitted to 18k listings (aggregates only) | cc5k+synth vs cc5k wall F1 .781 vs .769 and .751 vs .747, half-width .013-.017 | CPU render; skia | 4 to 5 | elements, rooms, scale | none (generator); authors' own ckpts yes | try: only MIT generator with fixture boxes and degradations |
| 2 | RF-DETR with DINOv2 init | transfer (general detection) | arXiv 2511.09554, v2 Feb 2026 | roboflow/rf-detr, Apache-2.0 | HF Roboflow/rf-detr-large Apache-2.0; XL, 2XL PML | COCO, Objects-365 | COCO APS 35.8 (DINOv2-S) vs 32.3 (CAEv2) | 384-704 px per size; consumer GPU via grad accumulation | 2 to 3 | elements | no (COCO ckpts); RF100-VL sets unknown | try: backbone evidence plus clean licences |
| 3 | Depiction re-render and degradation whitelist | ours plus transfer | Autom. Constr. 191 (2026); Augraphy 2022 | Augraphy MIT; fpgen MIT | none | our dev labels (record 0003) | Carrara: AP75 loses far more than AP50 under scan depiction | on loader | 1 to 2 | elements | none if only dev images; Carrara ckpts yes | try: aims at the measured failure |
| 4 | ResPlan | ours | arXiv 2508.14006, Aug 2025 | m-agour/ResPlan, code MIT | data CC BY 4.0 in LICENSE, **CC BY-NC-SA 4.0 in croissant.json**, issues open | traced from listing renderings, South Asian | benchmark room labelling only | n/a | 3 to 4 extra | rooms, elements via renderer | none | maybe: no fixtures, one bathroom class |
| 5 | ModRes cleaned ResPlan | ours | arXiv 2610.17178, Oct 2026 | emmashelley/ModRes, MIT | CC BY 4.0 (arXiv page) | 8,431 of 17k | graph statistics only | n/a | 3 to 4 extra | rooms | none | maybe: cleaner subset, same limits |
| 6 | benikm91 synthetic furnished plans | ours | HF, Oct 2026 | repo has no licence | HF card CC BY 4.0 | generated, 1M plans, 256 px | none reported | 256 px | 1 | elements | none | maybe: smoke test and rare-class pretrain |
| 7 | FloorPlanCAD | ours | ICCV 2021 | site: annotations CC BY-NC 4.0; authors do not own drawings | Drive links; HF re-uploads tagged CC BY-SA (conflict) | CAD, 15,663 drawings | PQ on vector input; not raster counts | n/a | 3 | elements | none known | maybe: local pretraining only, never shipped |
| 8 | ArchCAD-400K | ours | arXiv 2503.22346, NeurIPS 2025 | ArchiAI-LAB/ArchCAD, ACADEMIC USE ONLY LICENSE | HF gated, 40K subset | 5,538 CAD drawings | pretrain gain only in a figure (30 vs 50 epochs) | n/a | 4+ | elements | none known | skip: academic-only licence, no window class confirmed, vector |
| 9 | DINOv3 | transfer | arXiv 2508.10104, 2025 | facebookresearch/dinov3, "DINOv3 License" (custom) | same licence; HF cards gated | LVD-1689M, SAT-493M | COCO frozen-backbone 66.1 mAP [R] | ViT-S to H+ | 2 | elements | none | skip for shipped code: the custom DINOv3 License (read in full 2026-11-14: limited, non-transferable grant, redistribution under the same terms, acknowledgement in publications, trade-control clause) is not on record 0006's list of allowed licences (MIT, BSD, Apache-2.0, ISC, unmodified LGPL); no drawing evidence either |
| 10 | DINOv3 plus DPT floor-plan encoder (MMFE) | ours | arXiv 2609.12723, Sep 2026 | none linked | none linked | CubiCasa5K, Swiss Dwellings, ZInD, Aria | correspondence accuracy on Structured3D | 256 px, RTX 4090 | n/a | none | **yes** | skip: leak, no door or window task |
| 11 | Wall readout and emission nets of 2608.25608 | ours | 2026 | fpvec-lab MIT | none | cc5k, synth, Structured3D layouts | wall F1 .818 / .790 (CubiCasa5K test) | n/a | n/a | rooms outline | **yes** | skip for scored runs: trained on CubiCasa5K |
| 12 | Carrara robustness checkpoints | ours | Autom. Constr. 191 (2026) | andreacar/floorplan-detection-scan-robustness, code MIT, assets NC | "publicly released" (abstract) | CubiCasa5K | AP50/AP75 vs depiction | RT-DETR | n/a | elements | **yes** | skip checkpoints; use the finding |
| 13 | SynthPID topology-seeded generator | transfer: P&ID | arXiv 2604.16513, Apr 2026 | stated as git@github.com:LatentSpaceIITB/SynthPID; `gh api` returns 404 and `gh search repos` finds nothing (checked 2026-11-14), so no usable code | unknown | 665 synthetic from 12 real seeds | edge mAP synth-only 63.8, oracle 69.4, mixed 72.6 (OPEN100) | patches | idea only | idea | none | maybe: idea of seeding from real structure |
| 14 | Relationformer P&ID, synthetic vs mixed | transfer: P&ID | arXiv 2411.13929v2, DSAA 2025 | none linked | PID2Graph on Zenodo, licence not read | 170,944 synthetic patches; fine-tune 60 real + 500 synthetic | symbols mAP OPEN100 26.67 synthetic-only, 73.49 mixed | patches 1500 px to 512 | idea | idea | none | maybe: the mixing evidence |
| 15 | DETR backbone pretraining on synthetic P&ID | transfer: P&ID | ERAMIARS 2025 (SBC) | none | none | 700 sheets + 300 grids, 40 classes | mAP .905 synthetic, .338 IPD, .040 OPEN100 (COCO init) | 640 px crops, RTX 3060, 70 h | idea | idea | none | skip: the gap itself is the lesson |
| 16 | Line-drawing pretraining | transfer: vision | arXiv 2508.06696, Aug 2025 | none linked | none | STL-10, COCO sketches | VOC mAP 22.16 vs 18.17 at 10% data | ResNet-18 | n/a | none | none | skip: natural images only, no code |
| 17 | Polygon augmentation (polyaug) | ours | arXiv 2603.14764, Mar 2026 | Laudarisd/polyaug, MIT | n/a | 2000 Korean plans (AI Hub) | mIoU 88.4 to 90.8 (YOLOv11-Seg) | n/a | 1 | rooms | none | maybe: only for polygon outputs, no small-object test |
| 18 | SkeySpot DELP | ours (electrical) | arXiv 2508.10449, 2025 | HAIx-Lab/SkeySpot, no licence file (`gh api` license null) | none for data | 45 scanned plans, 2,450 instances | YOLOv8 mAP50 81.12 vs Faster R-CNN 48.62 | 200 epochs | n/a | n/a | none | skip: electrical keys, no licence |
| 19 | ResBIM | ours | Autom. Constr. 181 (2026) | RogerLiang0725/ResBIM, MIT | CC BY paper; data on GitHub | RPLAN-trained CNN generator, >1000 BIMs | none on symbols | n/a | n/a | none | none | skip: no fixture symbols, built on RPLAN |
| 20 | FloorYOLO | ours | Front. AI 9:1911589 (Sep 2026) | none stated | none | SESYD and CVC-FP only | CVC-FP mAP50 .8241 | 640 px | n/a | n/a | none | skip: no toilet class, no code |
| 21 | ROBIN, CVC-FP, SESYD | ours | 2015-2017 | ROBIN repo GPL-3.0 (data zips in it); CVC-FP site down; SESYD unread | unclear | 510 / 122 / 1000 | n/a | n/a | n/a | n/a | none | skip: licence unclear or GPL |
| 22 | HF repackages of CubiCasa5K and FloorPlanCAD | ours | 2024-2026 | n/a | tags apache-2.0, cc-by-4.0, cc-by-sa-4.0 on repackages whose parents are NC | CubiCasa5K, FloorPlanCAD | n/a | n/a | n/a | n/a | **yes** | skip: licence laundering and leak |
| 23 | Floor Plan CIS (MitUNet) | ours | arXiv 2512.02413, MVA 2026 | aliasstudio/mitunet, MIT | Zenodo record 17871080, **CC BY 4.0**, 23 MB zip | 500 raw real-estate plans (Russia and CIS), wall masks only | wall mIoU 87.91 scratch, 88.75 after CubiCasa5K pretrain (validation split, no test) | 512 px | 1 | none (walls only) | none (the model's pretrain checkpoint, not released, is CubiCasa5K) | maybe, with a rights caveat: 500 real raw plans tagged CC BY 4.0 by the uploader, but the Zenodo text says they were collected from real-estate listings, so third-party rights in the drawings are unclear (same issue as ResPlan); usable unlabelled (self-supervised or hard negatives), no fixtures |
| 24 | CubiCasa5k-ScanShift | ours | Autom. Constr. 191 (2026); Zenodo 18890483 | scripts "released", not located | Zenodo, **CC BY-NC 4.0**, 4.68 GB | CubiCasa5K clean vs scan pairs | AP75 and AP@0.85 fall more than AP50 (abstract) | RT-DETR | n/a | elements | **yes** | skip for scored runs; use as the diagnosis |
| 25 | Permeability-graph pipeline weights (openings detector, room and wall segmenters) | ours | Zenodo 22169669, Aug 2026 | code and weights in the release, CC BY 4.0 | CC BY 4.0 on the release; trained on CubiCasa5K official 4200/400/400 | CubiCasa5K | not read (paper not opened) | n/a | n/a | rooms, openings | **yes** | skip: leak despite the CC BY tag |
| 26 | FP-TXT text annotations | ours (text) | Zenodo 7921780, 2023 | n/a | COCO boxes "machine-printed"/"handwritten" for CubiCasa5K, CVC-FP, BRIDGE; no licence field | 1.3 MB | n/a | n/a | n/a | rooms labels (pointer to lit-ocr) | **yes** (CubiCasa5K images) | skip here |
| 27 | Aurinkolahti apartment data, Helsinki | ours | Zenodo 19894248, May 2026 | n/a | CC BY 4.0 spreadsheet of 622 units (3,787 apartments), no images | public building-permit drawings | n/a | n/a | n/a | none | none | skip: a layout-statistics source for Finnish room programmes only |
| 28 | AntPlan (Architect-Ant) | ours | arXiv 2606.10953, Jun 2026; HF OldDelorean/AntPlan, Oct 2026 | no code found | HF card **CC BY-NC 4.0**; paper page CC BY-NC-SA | 505 real professional plans, 26,716 object boxes, 92 classes (sink, toilet, stove, shower, bathtub among them); structure boxes proposed by a CubiCasa5K-trained detector then reviewed | none for detection (furnishing task) | **no source images distributed**, only schematic SVG renderings and YOLO-format boxes | n/a | elements, rooms | labels only: structure boxes came from a CubiCasa5K detector | skip for training; maybe as fixture-count and placement statistics for the generator (NC) |
| 29 | 2DPlan2Strct (RF-DETR Medium floor-plan checkpoint) | ours | HF OsamaMo/2dplan2strct, Sep 2026 | inference script, requirements only; repo licence text: non-commercial research and evaluation only | checkpoint_best_ema.pth 134 MB, **non-commercial** USAGE_TERMS | training set not stated (validation 2,964 images) | wall, room, door, window; box mAP50 94.52, mAP50:95 82.58 on its own validation split (reported by the author) | 576 px; T4 16 GB, 16 h, best EMA after epoch 13 | n/a | elements (door, window only) | **unknown** (data not named; floor-plan sets of this size are usually CubiCasa5K or Roboflow repackages) | skip: NC, unknown training data; only anchor is RF-DETR-M trained 13 epochs in 16 h on a T4 |
| 30 | DoorDet | ours | arXiv 2508.07714, 2025 (journal version 2026) | not checked | 4,991 CubiCasa5K plans re-rendered from the SVGs with door-type labels (full page re-read 2026-11-14 [V]); licence not found | CubiCasa5K | door detection then a VLM names the type | n/a | n/a | elements (doors only) | **yes** | skip: CubiCasa5K derived, doors only, plus a VLM step |

### 2b. Real fixture-level boxes found late (AntPlan)
- Architect-Ant (arXiv 2606.10953, Jun 2026, full HTML [V]) introduces AntPlan: 505 real professional residential plans, 4,495 room boxes and 26,716 object boxes in 92 classes, bathroom 4,145 and kitchen 5,485 objects, collected from publicly accessible sources. The card (HF `OldDelorean/AntPlan`, read through the Hub API and raw README [V]) is **CC BY-NC 4.0** and distributes **no source images**: only schematic SVG renderings and YOLO-format boxes (the single raw image is a README example). The authors say the furniture labels are pseudo-labels reviewed by hand, not exhaustively verified, and CubiCasa5K's own furniture classes are "coarse ... some fixtures represented only by partial symbols". Use: only as a source of fixture counts and placements per room type for the generator (non-commercial, so local use only); not a training set for a detector on images. Found through a search for synthetic fixture generators; it is the only 2026 real fixture-level plan set I found.

## 3. From other fields: the transfer notes (only those I opened; angle b covers the rest)

### 3.1 P&ID and engineering diagrams: sim-to-real gap for symbol detection
- Field and task: symbol detection and graph extraction on piping and instrumentation diagrams. Our object here: a valve
  or pump symbol is a toilet or window cell; both are small repeated symbols on thin lines.
- Measured: Stürmer et al. (arXiv 2411.13929v2, DSAA 2025, [V]): Relationformer pre-trained on 2,000 synthetic sheets
  (170,944 patches), fine-tuned on 60 real P&IDs plus 500 synthetic, about 37% of training patches real. Test on the 12
  real OPEN100 sheets, IoU 0.5: **synthetic-only** symbols mAP 26.67, nodes AP 34.35, edges mAP 44.49; **mixed** 73.49,
  82.18, 76.79 (the printed table header does not match its columns, so the metric mapping is inferred from the paper's
  Table III, where the mixed OPEN100 row matches exactly). Real-only is not reported. Enlarging the patch from 1500 to 2000 px cost "at least 10%" on symbols,
  and gave 9.49% gain on symbols on a subset where every symbol fits one patch (their words).
- SBC ERAMIARS 2025 [V, 4 pages read in full]: DETR (ResNet-50) on 700 synthetic sheets plus 300 grids of 40 classes,
  640 px crops at 50% overlap, trained 70 h on an RTX 3060: mAP 90.5 on the synthetic test, **33.8** on a two-sheet real
  set, **4.0** on OPEN100 (COCO init); ImageNet init 52.4, 25.1, 1.9; a classifier pre-trained on the 40 synthetic symbols
  91.6, 35.3, 4.9. Domain-specific pretraining adds about 1 mAP point; the gap is the story.
- SynthPID (arXiv 2604.16513, Apr 2026, [V, full page]): seeding the generator from the topology of 12 real sheets
  (node jitter, same-class template swap, Manhattan re-routing; 12,000 attempts gave 665 accepted images after
  Weisfeiler-Lehman and perceptual-hash deduplication) gives synthetic-only edge mAP 63.8 against 69.4 for a 12-real-
  sheet cross-validated oracle and 72.6 mixed. The paper claims a 30-point gain over random template scatter but that
  comparison is cross-paper, not a rerun; there is **no ablation of which randomisation mattered**; line width, fonts and
  photometric noise are not used at all.
- Why it should transfer: same shape, symbols on lines at small size, and the authors name the same cure (real
  structure plus a handful of real sheets). What breaks on our images: P&ID has one symbol set from standard
  libraries, ours has dozens of drawing styles; our real set is **thousands** of images, so the "mix in a handful of
  real" regime is not ours; Finnish labels and exact 90/180 rotations are absent from these papers. Use: the idea only.

### 3.2 Document layout with general-document pretraining (AEC drawings, arXiv 2607.18997, EC3 2026)
- [V, full PDF text]: on the 551-drawing FELD set, DocLayout-YOLO initialised from DocLayNet and DocSynth weights
  scores mAP50:95 0.589 and F1 0.662, which the authors read as "domain interference" (document-layout priors "act as a
  negative prior"). Caveat: the comparison changes architecture and weights together (DocLayout-YOLO against YOLOv12 at
  0.755), and the paper has no clean same-architecture on/off pair, so treat it as a warning, not a measurement.
  RF-DETR-M, 1344 by 800 px, no augmentation: mAP50 0.949. Layout regions, not symbols. Transfer: do not start our
  symbol detector from a document-layout checkpoint (DiT or DocLayNet style); start from COCO-pretrained DINOv2.

### 3.3 Natural-image line-drawing pretraining
- arXiv 2508.06696 [V, full]: pretraining on line-drawing versions of STL-10 raises PASCAL VOC detection mAP from 18.17
  to 22.16 at 10% of the data and matches the full-data baseline at 90%; backbone ResNet-18; no code or weights URL. On
  natural images only; for us it is an idea (train a first stage on thinned edge maps) with no code to reuse.

### 3.4 Frozen foundation descriptors under rendering shift
- Kuklev, arXiv 2609.24565 [V, full page]: on architectural hatch matching, frozen DINOv2-B scored 0.757 where a
  5.9k-parameter task CNN scored 0.959 on clean renders; under clean-to-scan shift the CNN lost 0.188 and a frozen fly
  descriptor 0.030. Lesson: a frozen general backbone is not enough for drawings, task training is needed, and the
  shift hurts the trained network most, which supports augmenting depiction (rank 3).

### 3.5 Optical music recognition trained on rendered scores only (Transcoda, arXiv 2605.10835, May 2026)
- Field and task: end-to-end OMR; what plays our object: a note head or rest on staff lines is a window cell on a wall
  line, a sparse symbol on thin lines. Opened with a verbatim read of the whole HTML page including Appendix A [V]. Appendix A shows that line
  weights are also randomised **at render time**, not only afterwards: staff-line width U(0.10, 0.26), stem width
  U(0.10, 0.36), bar-line width U(0.16, 0.72), ledger lines U(0.10, 0.40), page scale an integer in 52 to 84 (ranges, so
  a factor of 2.6 on staff lines and 3.6 on stems), which is the analogue of drawing our plans with several wall and
  symbol line weights (fpgen's thickness classes) before any degradation. Code: https://github.com/btrkeks/transcoda, **AGPL-3.0** (`gh api`, pushed 2026-11-13): not reusable for us.
- Setup: **synthetic only** (310,554 rendered pages, Verovio, 1485 by 1050 px input, ConvNeXt-V2-tiny), real scans
  never used in supervised training (about 200,000 unlabelled IMSLP scans used for FCMAE self-supervised pretraining).
  Randomisations: affine, perspective and stretch; synthetic paper background with texture, lighting gradient and colour
  cast; Augraphy ink bleed, mottling, dirty rollers, shadow, JPEG; injected non-target notation (dynamics, tempo text).
- Measured on 102 real scans (OMR-NED, lower is better, greedy decoding): full recipe 65.76; without the asymmetric
  augmentation 78.99 (+13.23); **without visual degradation 76.95 (+11.19)**; without score concatenation 80.10
  (+14.34). Self-supervised FCMAE pretraining on the real scans, two epochs: 60.70. Zero-shot real scans OMR-NED: Transcoda
  63.97, SMT++ 80.16, Legato 86.73 (beam search). So **degradation was worth about 11 points on real scans in a setting
  with zero real labels**, and the real-image self-supervised stage another 3 to 5. Caveat from the paper: the real
  scans overlap the validation split used for model selection.
- What breaks on our images: music staves are regular and the target is a token sequence, ours is a set of boxes on
  irregular drawings; the unlabelled real-scan pretraining needs real scans, and ours would be the dev images plus the
  500 Floor Plan CIS plans (CC BY 4.0), which is a new self-supervised option for us. Idea only; code for OMR is not reusable.
  (Optical music recognition is also listed for angle b of this scope; I read this paper because it measures which
  randomisations mattered.)

### 3.6 Document key-information localisation with Augraphy (arXiv 2502.06132, Feb 2025)
- [V, full page]: Augraphy ink-bleed, letterpress, low-ink, JPEG and dirty-screen effects (each at 70%), five augmented
  copies per document, ±5 degree rotation, trained on digital documents only and tested on digital and handwritten:
  mAP on handwritten changes 0.2799 to 0.3196 (ResNet-101 Faster R-CNN), 0.3566 to 0.3231 (Mask R-CNN), 0.5838 to 0.5957
  (DiT), 0.4722 to 0.5092 (LayoutLMv3); digital mAP falls 0.7239 to 0.7063 and 0.7354 to 0.7298 for the ResNet models.
  The text says three of four improved, the table shows the Mask R-CNN row fell. Lesson: Augraphy gave small and
  inconsistent changes when the shift was digital to handwritten; it is not a magic fix.

### 3.7 Historical map segmentation with synthetic pretraining (Petitpierre PhD thesis, EPFL 2025, arXiv 2511.19538)
- Field and task: semantic segmentation of scanned historical maps (built, non-built, water, road, contours). A thin-line
  cartographic drawing scanned from paper, so the nearest "line art plus scan" case with a measured synthetic ablation.
  Read as a 396-page PDF extracted locally (the arXiv HTML 404s); the ablation table and its caption [V]; the rest of the
  thesis not read.
- Setup: Mask2Former with Swin-L on 768 by 768 samples, trained on 1,006 real annotated map samples (Semap: 1,439 in all,
  144 test) after pretraining on synthetic maps drawn from GIS vector data with style transfer. Test mIoU 74.2 for the
  full recipe; **without synthetic pretraining 69.1 (-5.1)**, without fine-tuning 69.1, without multiscale 70.0 (Table 6
  [V]). 150 h to converge on a 12 GB Titan X (reported by the author).
- Why it matters: with about 1,000 real images the synthetic stage was worth 5 mIoU points, while our 3,300 real
  CubiCasa5K plans plus 3,327 synthetic ones moved wall F1 by under 1.3. Together with the P&ID numbers this suggests the
  benefit falls quickly as real data grows past a few thousand images. We have 3,828 dev images, so we are on the
  flat part of that curve for the common classes and on the steep part only for rare ones (bathtub 312 boxes).
- What breaks on our images: segmentation of regions, not exact counts of small symbols; synthetic maps came from real
  GIS geometry, ours would come from generated layouts; no licence read for the thesis code or data.

### 3.8 PCB schematics (adjacent field, abstracts only)
- PCBnet (arXiv 2608.27923, Aug 2026) [V, abstract via arXiv API]: 300+ real designs, 50k+ component instances, detection mAP 94.54, trained on real designs; OmniSch (arXiv 2604.00270, Mar 2026, CC BY-NC-SA 4.0 per its arXiv page) [V, abstract]: 1,854 real schematics, a benchmark for large multimodal models. Neither measures synthetic-to-real transfer; a search for 2026 hand-drawn-circuit augmentation benchmarks found only the older DFKI CGHD set (camera photos, Faster R-CNN baseline) and a vendor blog (RF-DETR, 3,800 P&ID diagrams, 99.2 mAP50, vendor claim, not relied on). Result: no new evidence on synthetic data here; the P&ID notes in 3.1 stay the nearest case.

### 3.9 Mechanical engineering sketches and drawings (adjacent field, abstracts only)
- Bickel et al., Applied Sciences 14(14):6106 (Jul 2024, CC BY 4.0) [V, abstract through Crossref; MDPI and the FAU page refuse automated access, so no numbers]: six synthetic-data generation types compared across six one- and two-stage detectors for symbols in principle sketches, evaluated on two unseen test sets (gearbox variants, CAD-derived assemblies). It is the only study I met that compares generation types head to head for symbol detection, but I could not read which type won. A January 2026 PHM Society paper (vision-language pipeline on CAD-rendered synthetic data, 95.2 AP on real CAD sheets, abstract in a search result only) also uses synthetic rendering and domain randomisation. Open for angle b or a later round with a human-run browser; no ranking depends on them.

### 3.10 Tile-based training for small floor-plan symbols (Rezvanifar et al., CVPRW 2020, arXiv 2006.00684; older, read for the tiling recipe)
- [V, full PDF text]: 115 real apartment units from architects' PDFs rasterised at 150 DPI (whole plans about 5400 by 3600 px, a bathroom sink symbol about 70 by 80 px), 12 symbol classes, dataset **not released** for intellectual-property reasons. Tiles of 224 to 227 px at stride 50 px, kept only if they contain at least one complete symbol (90 units gave 4,707 tiles, 80/20 train and validation, 25 held-out whole plans); a scale parameter lets a larger window be resized to the network input. The tile stage doubles as augmentation, since a symbol appears at many positions. YOLOv2 with a ResNet50 backbone: tile-validation mAP 72.40, AP50 96.20, AP75 90.13 (Darknet19 61.53 and Xception 51.03); on the 25 whole plans the global mAP is about 59 (the table prints 59.03 and 56.50, I did not map the two columns). Also on SESYD with its GREC degraded versions, where thinner and thicker lines are among the noise levels, the same family of shift that Carrara measures.
- Transfer: a symbol here is several times larger in px (70 by 80) than our 5 to 20 px ones, so their tile-to-symbol ratio does not carry over; the point that carries over is the recipe (tile at native resolution, keep tiles with a complete symbol, overlap, tile-level augmentation, whole-plan evaluation on held-out plans, and the whole-plan score being lower than the tile score).

### 3.11 A negative case study on hand-written plan generators (Zenodo 23000152, Apr 2026, CC BY 4.0)
- "Floor-Plan Understanding Under Data Scarcity: A Case Study of Detection, Retraining and Synthetic-Data Generation" [V, full PDF, 11 pages, single author, no code, no measured metrics]: six strategies tried in turn for detecting walls, doors, windows and rooms in house plans (classical vision, Mask R-CNN from a public floor-plan model, heads-only retraining on hand-annotated plans, a rule-based generator, a genetic algorithm over binary-space-partitioning layouts, an LLM idea). Reported failure of the generators: loose room rules gave unrealistic plans, strict rules gave a stuck search and repetitive plans (the authors' words), so the synthetic data never reached training use; the retraining stage failed for lack of labelled polygons. Why it matters for rank 1 and 4: layout realism and diversity is the weak point of rule-written generators, which is the argument for fpgen's statistics fitted to 18k listings and for real layouts from ResPlan or the 2k to 3k dev plans' room structure, rather than hand-written rules; but it is an anecdote, not an ablation.

### 3.12 Clean reference symbols to real drawn symbols with domain adaptation (arXiv 2609.07159, Sep 2026, CC BY 4.0)
- [V, full HTML page, 45 kB]: De Gregorio, Fornés, Kang and Megyesi, "Unsupervised Domain Adaptation for Symbol Spotting in Historical Encrypted Manuscripts": the query symbols exist only as clean **font glyphs**, the targets are handwritten symbols on 14 manuscript pages from 7 collections (DECODE database), no labelled target examples. A ResNet-50 encoder is trained with supervised contrastive loss on glyphs plus a domain-adversarial (gradient reversal) loss across glyphs and unlabelled manuscript crops, then an embedding-space style adaptation at retrieval. Table 1, P@1 at threshold 0.70 (their retrieval metric, not detection): zero-shot ResNet-50 0.130, DINOv2-base 0.222, DINOv2-large 0.127, CLIP ViT-L/14 0.401; glyph-trained ResNet-50 baseline 0.457; full method 0.595. Ablation (Table 2): baseline 0.457, plus contrastive 0.484, plus adversarial 0.525, both 0.586, plus adaptation 0.595. Note the frozen DINOv2 vectors at the bottom of the table, which matches Kuklev's finding (3.4) that frozen general backbones fail on drawings.
- Transfer and limits: this is the one 2026 symbol result I met where the source domain is **clean reference symbols** and the target is real drawn symbols, as with fpgen glyphs or template crops against our sheets; it needs unlabelled target images (for us dev-split images only; eval-split images must stay out, record 0003), classifies given crops rather than detecting boxes on a sheet, is tested on 14 pages, and I found no code link in the page. Idea for a second stage after detection (reclassify detected crops, for example sink against shower), not for the first number.

## 4. What to assemble tonight, and how much synthetic helps (the scope question)

Best commercial-safe set in a night, in order of use:
1. **Our own dev labels** (3,828 images, about 104k boxes), the only real, Finnish-style source, allowed by record 0003
   for dev-split images. This is the training backbone; every synthetic source below is a supplement.
2. **fpgen renders** (MIT) at 855 px longest side for 3 to 5 k plans, mixed 1:1 or lower with real, for bathtub (312
   real boxes) and the sauna stove (2.5k) after we add two glyphs and a Finnish label vocabulary, plus rot90 and flip.
3. **Depiction jitter** (rank 3) applied to both real and synthetic.
4. Optional: ResPlan or ModRes polygons as layouts, and a 50k subset of the benikm91 set for a quick pretrain.

Correction of emphasis after re-reading record 0003 and the context file (2026-11-14): the dev and eval images **are** the CubiCasa5K originals, i.e. the *scanned depiction* of Carrara's study. A detector trained on dev images already sits in the "scan-trained" column (window plus door AP50 0.751, AP75 0.599 for RT-DETR on the CubiCasa5K test split, a reference level, not our metric); the clean-to-scan failure bites only for (a) anything clean-rendered that we add: fpgen renders, ResPlan renders, SVG re-renders of dev layouts, and (b) drawing styles outside CubiCasa5K that the pipeline may meet (about a third of the questions are not the CubiCasa templates). So depiction jitter is a **requirement for the synthetic supplement and an insurance for unseen styles**, not a likely gain on dev-to-eval inside CubiCasa5K. Test it that way: measure the supplement with and without jitter on dev, and keep the real-only run as the control.

Run order that follows from the evidence (all numbers read per class on dev, real-only run as the control; hours are my estimates):
1. Real-only RF-DETR (Apache sizes, DINOv2 backbone) on dev tiles at native resolution, default augmentation plus exact rot90 and flips; time one epoch first because of issue #974 (1 to 3 h). This is the number every other arm must beat.
2. Same plus depiction jitter on real images (dilate 1 to 2 px, blur, down-up 0.55 to 0.9, JPEG 40 to 92): expect no gain inside CubiCasa5K; its job is to show it does no harm (1 h of loader work).
3. Add fpgen renders (3 to 5k, our class map, Finnish labels, sauna-stove glyph, down-scaled to the 5 to 20 px regime, **with jitter and a dilation op we add**) at 1:1 or less: read bathtub, sauna stove, shower AP and the count error per class (3 to 4 h adapter plus one run).
4. Same arm without jitter: shows whether the jitter matters for the clean supplement, per Carrara's clean-model collapse (one more run).
5. Only if 3 helps a rare class: ResPlan or ModRes layouts as fpgen's layout source, local training only until the licence is settled (3 to 4 h).
6. Threshold and tiling check for exact counts: overlapping tiles with box merging, threshold swept on dev for recall (issue #1599 and the AEC recall of 0.800 are the reasons).

Idea from the last searches, not tested anywhere I read: **copy-paste of our own real crops** for the rare classes. Paste dev-split crops of bathtub (312) and sauna stove (2.5k) onto other dev plans at empty wall-free spots, with the paste boxes as labels; the patents found describe the same for engineering schematics (symbols copied between schematics without overlap, or placed into diagram backgrounds), and Jamieson, Elyan and Moreno-Garcia, "Few-Shot Symbol Detection in Engineering Drawings" (Applied Artificial Intelligence, Sep 2024, CC BY 4.0 per Crossref) trains from fewer than ten instances per class; I could not open that paper (publisher and repository return a Cloudflare challenge), so its method and numbers are unread. This needs no generator, no new licence and no Finnish glyph drawing, at the price of unrealistic context (a bathtub outside a bathroom); half a day at most, est. 2 h for a first version.

How much synthetic helps in the papers that measured it:
- **Thousands of real images**: negligible. +0.4 to +1.2 wall F1 on CubiCasa5K test (n = 296 plans, 287 on the common roster of the cc5k-versus-mix comparison) with per-system half-widths of 1.2 to 1.8 points in the main text and 1.3 to 1.7 in the appendix tables (arXiv 2608.25608 [V]). The same paper trained with Structured3D layout pretraining but reports no
  ablation of it.
- **About a thousand real images**: +5.1 mIoU from synthetic pretraining in scanned historical-map segmentation (Table 6 of
  the Petitpierre thesis, section 3.7).
- **Tens of real images**: large (P&ID symbols mAP 26.7 to 73.5), but synthetic-only collapses (4.0 mAP on OPEN100).
- **Floor-plan generation**, not recognition (arXiv 2607.06483, Sep 2026, [V, full page]): synthetic pre-training with
  135k procedurally packed scenes beats real cross-domain priors at 1k real examples (mean position error 7.05 vs 12.1
  on RPLAN, 13.7 vs 19.7 on MagicPlan) and converges with them on Swiss Dwellings; **no real-only baseline** and no
  code. Different task, so it only shows that synthetic priors can beat a wrong-domain real prior.
- No paper gives a clean "augmented vs not" number on real degraded drawings; this campaign's earlier note reached the
  same conclusion and I found nothing newer that changes it.
- Rule from all of them: report the effect on **our dev split per class** (bathtub, sauna stove, door, window) before
  keeping any synthetic source, since the main score is unlikely to move.

## 5. Looked for and did not find

- Any 2025-2026 raster floor-plan dataset with toilet, sink, bath and stove boxes that is both **real** and openly
  licensed for commercial use. Searches for a 2026 release returned only the NC sets, repackages and re-uploads.
- A paper that trains a detector on synthetic floor plans and tests on **real raster floor plans with fixture classes**:
  none. Mishra et al. 2021 (SFPI, 10,000 synthetic images, mAP 99.8 on SFPI, 98.1 on SESYD, [V from the PDF text]) has no
  real-image test at all. The 2023 Sensors emergency-plan study (synthetic plus real) is blocked by MDPI and was not read.
- Self-supervised pretraining (MAE, DINO, contrastive) **on drawings** evaluated on detection: none. Nearest hits are
  FloorplanMAE (arXiv 2506.08363, a generation-task MAE that reconstructs masked floor-plan regions, abstract opened [V]) and the floor-plan contrastive
  encoder that includes CubiCasa5K (arXiv 2609.12723, rank 10).
- Stroke-width or line-thickness augmentation tested against a digital-to-scan shift on drawings (searched again 2026-11-14, extended mode): nothing dated 2025-2026 beyond the Carrara tables; older P&ID and symbol papers only.
- Clean-to-scan **domain adaptation** for floor-plan symbols: none. arXiv 2607.00015 (May 2026, Australian apartment compliance checking, abstract opened [V]) is a conceptual framework paper with no detection results.
- Scan of the Hugging Face Hub for floor-plan datasets created June 2025 to November 2026 (Hub API search on six spellings, 2026-11-14): nothing with fixture boxes on real images and a clean licence. Opened: `JoaoMigSilva/floorplans` (MIT tag, 9.5k PNG, I viewed one: **synthetic colour-block toy plans** with circular site labels, no fixtures, unlabelled: skip); `G-list/floor_plans` (MIT tag on an empty template card, 2.2k PNG with generated captions, the one I viewed is a **real Japanese housing drawing**: provenance and rights unknown, copied from a Kaggle set: skip, licence laundering risk); `OldDelorean/FloorplanQA-Layouts` (CC BY-4.0, JSON layouts of rooms and objects for LLM spatial reasoning, no images: skip); `Tristan12138/cubicasa5k-skv4` (CC BY-NC-SA 4.0, CubiCasa5K-derived: leak); `v1nz/cubicasa5k-yolo` (CC BY-NC 4.0, CubiCasa5K YOLO conversion: leak); `jotamunz/synthetic-floorplans-*-captioning` (CC BY-4.0, Nov 2026, captioning sets on synthetic plans, not opened beyond the metadata).
- HomeWorld (arXiv 2606.06390, Jun 2026, page read [V]): 300K "real-world residential floorplans" curated from 1.084 million images scraped from an online real-estate repository, labelled by a detector trained on 2K manual annotations; the dataset is only "will publicly release", no licence, 3D-scene purpose: skip, and a rights risk like the listing sources behind ResPlan.
- A second open generator with fixture symbols: a search for MIT or similar procedural plan renderers found only 3D tools (Infinigen Indoors), a drafting library whose floor-plan engine draws toilet, sink and bath symbols (Schematex, licence not checked, a drawing tool and not a data generator) and the Delft benchmark whose preprocessing removes fixtures. A Technion cGAN paper on bathroom furniture layouts (Buildings 2023, 1,290 image pairs; read from its PDF [V]) generates layouts and is no detector data. arXiv 2509.17283 (facility counting by door detection plus an LLM, abstract [V]) builds no training data. fpgen remains the only one.
- Zenodo 21642514 "Automated Data Extraction of Set Products from Floor Plans" (Jul 2026, CC BY 4.0, 7-page vendor poster, read [V]): YOLOv8 plus OCR for doors, windows, fixtures and set products, "80 to 90% detection accuracy" and "4,000+ floor plans processed" as marketing claims with no dataset, class list, metric definition or method detail; YOLOv8 is AGPL (record 0006 out-list). No evidence value.
- MLStructFP (Automation in Construction 2023, repo `MLSTRUCT/MLStructFP`, code MIT, pushed 2026-04-23; README read [V]): 954 large multi-unit structural plans with **wall and slab polygons only**, dataset delivered on request through a form, data licence not stated: no fixture classes, skip.
- Modified Swiss Dwellings (arXiv 2407.10121, Delft) and Swiss Dwellings: the context file says they are part of the Stoa test sources (a leak for scored runs), and the Delft preprocessing drops fixtures; not used. The curated list `yunusskeete/floor-plan-datasets` (README read [V]) names no dataset beyond those already covered.
- arXiv listing sweep by submission date, June to November 2026, on floor-plan and architectural-drawing terms (three queries, 2026-11-14): new items beyond those above are arXiv 2608.14317 (Aug 2026, Mask R-CNN detecting lighting symbols and light types on 2D plans, bbox mAP 0.7596, mAP50 0.985, abstract only [V]; no data or licence stated, electrical symbols) and ARCH-B 2609.34047 (multimodal benchmark of cross-representation building matching, not detection). DrawingVQA 2607.15418 and the other VLM benchmarks are for lit-vlm. No new paper on synthetic training data for floor-plan symbols.
- DINOv3-based real-time detectors as a way round RF-DETR: DEIMv2 (`Intellindust-AI-Lab/DEIMv2`, README read [V], pushed 2026-10-23) ships under its own "DEIMv2 License" (`gh api` NOASSERTION) because it builds on DINOv3, so it falls outside record 0006's list like DINOv3 itself; D-FINE (`Peterande/D-FINE`) is Apache-2.0 (`gh api`) but has no DINO backbone and was not otherwise read. Pointer for lit-detect only.
- Fixture box counts in ArchCAD-400K (class table is a figure) and a window class (not confirmed; the paper names windows
  only as an example) [V].
- FloorPlan8K (FloorPlanFormer, AAAI-26, 8,200 images, 77,434 instances): now **read** (full PDF from the AAAI OJS download link, 2026-11-14 [V]). Chinese floor plans gathered from property companies (rights unclear), COCO JSON, tasks are outer and inner contours, entrance doors and room types, **no fixture classes**. Code https://github.com/LTayfaker/FloorPlanFormer has **no licence file**; only the test and validation splits are linked on Google Drive, no training set. Verdict: skip.
- Result tables of the Carrara mitigation arms (augmentation fine-tunes): the repository has the scripts and a README but no result file; the paper text is blocked.
- Roboflow "Floor Plans 500" (R-FP500 repackage): pages are JavaScript-only for the headless browser; search results show
  CC BY 4.0 on one listing and MIT on a Kaggle copy for the same 500 images (conflict), classes door, window, zone only.
- CVC-FP page: still timing out (45 s) in the browser.

## 5b. Citation walks (forward), what they found

Routes: Semantic Scholar graph API (ResPlan, ArchCAD-400K, CADSpotting, Raster2Seq, CubiCasa5K, Augraphy, RF-DETR) and
OpenAlex `cites:` filters when Semantic Scholar throttled (ResPlan 15 citers, RF-DETR 140, ArchCAD 11, the Carrara study 0,
the fpgen paper 0). Read from the hits: ModRes, 2608.25608, ResBIM, TextCAD (full page), the AEC layout benchmark, the
Carrara study (abstract), the Zenodo records it led to, the two OMR and document-augmentation papers (Transcoda,
2502.06132).
- ResPlan forward: layout generation, 3D scene synthesis and room-graph papers (GFLAN, HomeWorld, MANSION, FZplan,
  VF-GraphSAGE, CANDO), the ModRes clean-up and the fpgen paper. **None trains a symbol detector on ResPlan renders**; the
  only raster use is 2608.25608.
- ArchCAD-400K forward (11): CADSpotting, TempFit (template-fitting symbol spotting), a rectangle-symbol keypoint paper,
  TextCAD, DoorDet journal version, DrawingVQA, a VLM small-object zoom paper (arXiv 2610.09313, for lit-vlm), an AEC
  VLM post-training paper (2609.34082) and a 2026 survey of vision foundation models for engineering documents (abstract
  only [V via OpenAlex]: it reports that models pretrained on natural images "must be adapted to thin-line,
  symbol-dense" documents and proposes "engineering-specific pretraining corpora" as a research direction, i.e. none
  exists yet).
- CubiCasa5K forward (176 via Semantic Scholar): about 70 papers dated 2025-2026; the data, robustness and synthetic ones
  are rows 1, 3, 10, 11, 17, 23 to 25 above. Segmentation papers (FGSSNet, MitUNet, LGS-FPP: SAM 2 based, mIoU 88.92 on
  CubiCasa5K but 69.58 on a scanned set, abstract only [R]) belong to lit-rooms.
- RF-DETR forward (140): the AEC drawing benchmark and several small-object DETR variants; no floor-plan paper.

Venue check (2026-11-14): the ICDAR 2026 accepted-papers list (page read in full, 26 kB [V]) has two items in this area, "GRaF-Net: a Multi-Branch Gated Residual Architecture for Floor Plan Semantic Segmentation" (segmentation, lit-rooms) and "Towards Scalable Knowledge Graph Extraction from Piping and Instrumentation Diagrams" (P&ID, titles only, not opened). Nothing on synthetic training data for floor-plan symbols; the 2025-2026 work on that topic sits on arXiv and in the repositories above rather than at the document-analysis venues. Journal route: Automation in Construction carries the Carrara study and ResBIM.

## 6. Leakage and licence ledger for every checkpoint or dataset mentioned

| Item | Trained on CubiCasa5K or a repackage? | Licence facts read |
|---|---|---|
| RF-DETR N, S, M, L, Seg (Apache) | no (COCO, Objects-365) | README and LICENSE, HF card apache-2.0 |
| RF-DETR XL, 2XL, Atto, Femto, Pico | no | PML 1.0, out |
| DINOv2 (Apache-2.0 card) | no | HF card read |
| DINOv3 | no | custom DINOv3 License, LICENSE.md read by fetch; HF card API says `license:other`, gated |
| fpvec-lab code and fpgen | n/a | MIT |
| 2608.25608 trained models | **yes** | none released |
| 2609.12723 MMFE | **yes** | none linked |
| Carrara checkpoints | **yes** | repository andreacar/floorplan-detection-scan-robustness: code MIT, weights and result bundles under a separate non-commercial LICENSE.assets |
| FloorPlanCAD labels | no known | NC annotations, authors do not own drawings; HF re-uploads claim CC BY-SA (the Voxel51 card's header says cc-by-sa-4.0 while its body says CC BY-NC 4.0, "non-commercial use only") |
| Floor Plan CIS | no | Zenodo record cc-by-4.0, read through the Zenodo API; images collected from real-estate listings, so the tag may not cover the drawings' authors |
| AntPlan | labels only | HF card CC BY-NC 4.0, no source images |
| 2DPlan2Strct RF-DETR-M checkpoint | unknown | non-commercial research and evaluation only |
| ArchCAD (HF subset) | no known | ACADEMIC USE ONLY LICENSE file, commercial prohibited |
| CubiCasa5K | is the leak | GitHub LICENSE CC BY-NC 4.0; Zenodo record cc-by-nc-sa-4.0 (the two disagree) |
| HF `*cubicasa5k*`, `floorplan-vlm-sft-dataset-flat` | **yes** (repackages) | tags apache-2.0, cc-by-4.0 on NC parents |

## 7. Open questions, and the tools that were missing

Questions for the orchestrator:
1. Is rendering the dev-split SVGs a second time in randomised depictions covered by record 0003 as "boxes exported from
   dev-split images", or does it need a line in the record? (It changes pixels, not labels.)
2. May we add fixture glyphs shaped like Finnish symbols to fpgen without a source image? We would draw them from the
   dev crops we already hold; that is dev-split data again.
3. Does the exact-count score need the sauna stove from synthetic data? 2.5k real boxes may already be enough.
4. For lit-detect, lit-count, lit-sheet (other scopes, one line each): arXiv 2610.09313 "Why VLMs miss small objects, and
   when zooming in is safe" and TempFit 2610.17776 (panoptic symbol spotting by template fitting) cite our papers and
   look relevant to L7 and L11; I read only their abstracts (2610.09313: VLMs miss small objects because of too few tokens per object and too much to report per call, with a splitting rule under overlap; TempFit: reformulates panoptic symbol spotting as template retrieval and pose fitting on vector CAD). VecFormer (arXiv 2505.23395), TextCAD (arXiv 2607.12678: FloorPlanCAD-V2
   with extracted text annotations, no release or licence stated, full page read 2026-11-14 [V]; PQ 91.09 against 88.14 for VecFormer on FloorPlanCAD-V2, and it also evaluates on CubiCasa5K) and PolarSym
   (arXiv 2608.11793) are vector-route papers for L11 and L5.

Tools missing or blocked:
- No arXiv MCP; used arxiv.org/html through web-fetch and, on truncation, the headless browser.
- Semantic Scholar's API answered for the first papers and then returned 429 on retries (for the fpgen paper and RF-DETR); OpenAlex's free daily budget for this network was used up during the campaign, and I did not request an API key, which would need the owner's email.
- MDPI, ScienceDirect, SSRN, Roboflow Universe, preprints.org and the FAU page (Anubis) refuse automated access, also from the headless browser; those sources are listed above as not read. The AAAI proceedings page blocks the browser, but its PDF download link worked with curl.
- Several web-fetch results were truncated at about 40k characters with the remainder summarised; those parts are
  marked [S] when they were not re-read; at the last count of this report none remain open, every earlier [S] part was re-read through the browser or a locally extracted PDF.
