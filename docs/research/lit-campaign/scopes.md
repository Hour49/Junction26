# Scopes: the 12 literature agents

Read [worker-brief.md](worker-brief.md) first. Each scope lists where to start, the adjacent fields to mine and
the question the report must answer. Names of papers, models and datasets are starting points written from memory:
confirm each one exists before citing it.

Owners: Bogdan's research orchestrator runs L1, L4, L6, L7, L10, L12. Tudor's orchestrator runs L2, L3, L5, L8, L9,
L11. See [README.md](README.md).

## L1 `lit-floorplan`: floor-plan recognition as a field
- The CubiCasa5K paper (Kalervo 2019) and everything that cites it and reports numbers on it: which classes, which
  metric, what is state of the art on CubiCasa5K today.
- Raster-to-Vector (Liu 2017), Deep Floor Plan Recognition (Zeng 2019), FloorNet, later multi-task and transformer
  models for floor-plan parsing; surveys of automatic floor-plan analysis.
- 2024-2026: "floor plan understanding", "floor plan parsing transformer", "floorplan foundation model",
  WAFFLE, floor-plan benchmarks for vision-language models. Find the source of the "40-55% exact on door and window
  counts" figure in docs/REQUIREMENTS.md §2 and say whether it holds.
- Adjacent fields: other "turn a technical picture into structured data" problems and what their best systems
  look like end to end: P&ID digitisation, electrical schematic and circuit-diagram recognition, historical and
  cadastral map digitisation, mechanical engineering drawings, optical music recognition, chart and diagram
  parsing, table structure recognition, indoor floor-plan reconstruction from lidar density maps. Which pipeline
  shape won there (modular, one multi-task model, image to markup), and did end-to-end models overtake modular ones?
- Answer: what does the best published system reach per class on raster plans, and with how much training data?

## L2 `lit-detect`: symbol detection, small and dense objects
- Real-time DETR family and successors, with licences: RF-DETR, D-FINE, DEIM, DEIMv2, RT-DETR v2/v3/v4, LW-DETR;
  non-AGPL YOLO lines (YOLOX, RTMDet, PP-YOLOE, YOLO-NAS weights licence); heavier Co-DETR, DINO-DETR.
- Small-object and dense-scene methods: SAHI and sliced training, high-resolution inputs, P2 heads, crowd detection.
- Oriented detectors (RTMDet-R, Oriented R-CNN) and whether rot90 augmentation makes them unnecessary.
- Detectors applied to floor plans and to engineering drawings (P&ID symbol detection is a large literature):
  per-class AP for doors, windows, sanitary symbols; training set sizes.
- Adjacent fields: tiny and dense object detection elsewhere: aerial and satellite (DOTA, VisDrone, AI-TOD),
  dense retail shelves (SKU-110K), optical music recognition (DeepScores: thousands of small symbols on staff
  lines, close to symbols on wall lines), PCB component and defect detection, circuit-diagram symbols, map symbol
  detection, math formula and chemical structure symbol detection, cell detection in microscopy. Look for what they
  do about symbols touching lines, symbols touching each other (our window strips), and extreme size ranges.
- Answer: which Apache/MIT detector gives the best small-object AP when fine-tuned on about 3.8k images, 12 GB GPU,
  in under 3 hours? What input resolution and slicing do papers on drawings use?

## L3 `lit-count`: counting
- Class-agnostic and exemplar counting: FamNet, CounTR, LOCA, DAVE, CACViT, GeCo, CountGD and successors, T-Rex2.
- Density-map and point-supervised counting (CSRNet line, P2PNet, PET); counting by detection vs by regression: which
  wins when counts are 0-40 and must be exact.
- Counting with vision-language models: CountBench, Pixmo-count, Molmo pointing, TallyQA-style results; papers
  showing where they fail.
- Text-prompted "segment every instance" models (SAM 3 and similar) used for counting.
- Count calibration: turning detection scores into a count distribution (Poisson-binomial), learned count heads on
  top of a detector, count supervision as an extra loss.
- Adjacent fields: fields where the exact number matters and is audited: cell and colony counting in
  microscopy, crowd counting, wildlife and livestock counts from drones, tree and crop counting, retail inventory
  counts, PCB component counts, pill counting, traffic counts. Look for how they get from "about right" to exact
  (point supervision, count-then-localise, human correction of a few marks), how they report exact-match rate, and
  any trick for adjacent identical objects.
- Answer: best published way to turn a decent detector into an exact counter; is per-plan exemplar counting ("two
  confident windows from this plan, find the rest") shown to beat a fixed detector under style shift?

## L4 `lit-rooms`: room outlines and vector reconstruction
- Polygon predictors: RoomFormer, HEAT, PolyRoom, FRI-Net, CAGE, SLIBO-Net, Raster2Seq, PolyDiffuse, FloorSAM-like
  work; which take a raster floor-plan image (not a point-cloud density map) as input.
- Wall segmentation and wall-graph extraction (MLSTRUCT-FP and its methods), room segmentation by type, panoptic
  models (Mask2Former, OneFormer) on floor plans.
- Room type from context: graph networks over rooms, fixtures-in-room rules.
- SAM, SAM 2, SAM 3 on line drawings: do automatic masks give usable rooms?
- Adjacent fields: closed-polygon extraction elsewhere: building footprints in remote sensing (PolyWorld,
  HiSup, frame-field learning, Pix2Poly and newer), land-parcel and cadastral map segmentation, historical map
  vectorisation, road and lane graph extraction (Sat2Graph, RNGDet, MapTR, VectorMapNet), table structure
  recognition (a cell bounded by ruling lines is a room bounded by walls), comic panel segmentation, cell membrane
  segmentation (closing gaps in thin boundaries, like door openings in walls). Look for how they close gaps in
  boundaries and how they regularise polygons to right angles.
- Answer: cheapest way to get room polygons good enough for (a) attaching a label to a room and (b) an area within
  about 5%; reported room IoU or area error on CubiCasa5K or R2V.

## L5 `lit-ocr`: text on drawings
- OCR for sparse, short, rotated labels on technical drawings and floor plans; low resolution (labels 8-15 px high).
- Engines and their licences and Finnish/Swedish support: PaddleOCR PP-OCRv5, RapidOCR, docTR, EasyOCR, Tesseract;
  detectors DBNet++, CRAFT; recognisers PARSeq, SVTRv2, TrOCR, CLIP4STR.
- 2025-2026 document vision-language OCR: GOT-OCR 2.0, PaddleOCR-VL, DeepSeek-OCR, olmOCR, dots.ocr, MinerU, and
  whatever leads OmniDocBench now. Do any handle scattered two-letter labels and return positions?
- Closed-vocabulary tricks: lexicon-constrained decoding, word spotting, treating each abbreviation as a detector
  class.
- OCR on engineering drawings: eDOCr, eDOCr2 and similar (dimension text, rotated text).
- Handwriting and historic Finnish/Swedish text (for the legacy archives; lower priority).
- Adjacent fields: text spotting on historical maps (the ICDAR MapText competitions, mapKurator and similar:
  short place names at any angle over line work, the closest analogue we know of), P&ID tag reading, scene text,
  text in charts and figures, licence plates and utility meters (short strings from a closed alphabet at low
  resolution), comic and manga text, sheet-music annotations. Look for rotation handling without a page-level
  orientation step and for lexicon use.
- Answer: expected accuracy on 2-4 character labels at 10 px height, and the cheapest fix (upscale, fine-tune,
  lexicon); a short list of Finnish floor-plan abbreviations with meanings, sourced.

## L6 `lit-scale`: scale, dimensions, areas
- Dimension-line detection and reading on architectural and mechanical drawings (eDOCr2, dimension extraction
  papers, GD&T extraction).
- Scale-bar detection and reading (also from map and microscopy literature).
- Scale from printed text plus paper size or scan dpi; inferring paper format from a scan.
- Metric scale from object priors (door width, fixtures) and learned scale regression on floor plans; any paper that
  reports scale error.
- Area computation from raster plans and its reported error; net vs gross area conventions in Finnish listings.
- Commercial quantity-takeoff tools (Togal.AI, Kreo, Bluebeam, Autodesk Takeoff, Werk24, others): how they set scale
  and what accuracy they claim.
- Adjacent fields: anywhere pixels get calibrated from marks in the image: chart data extraction (axis ticks
  plus tick labels give the calibration, the same structure as a dimension line or a scale bar: ChartOCR and later
  work, plot digitisers), scale-bar detection in electron and light microscopy, ruler detection in medical,
  forensic and fisheries photos, map scale bars and map georeferencing, photogrammetry and single-image metrology
  from objects of known size, roof and facade measurement from aerial images. Look for robust fitting when several
  marks disagree and for how the error is reported.
- Answer: which scale route is proven to within 2%, which only to about 10%, and how do others show the user that a
  scale is an estimate?

## L7 `lit-vlm`: vision-language models on drawings
- Benchmarks of frontier and open models on floor plans, CAD and engineering drawings (counting, spatial questions,
  reading dimensions): 2025-2026 papers; what accuracy, what fails.
- Small open models that can be fine-tuned on one 12-16 GB GPU, with licences: Florence-2, PaliGemma 2, Qwen2.5-VL
  and Qwen3-VL sizes, InternVL3, SmolVLM2, Moondream, MiniCPM-V, Molmo. Which output boxes or points natively.
- Fine-tuning for structured output (image to JSON), LoRA recipes, how many examples papers needed.
- Prompting tricks with measured gains: Set-of-Mark, tiling, zoom and crop agents (ViCrop, V*-style search),
  detector-then-verifier pipelines.
- Models on Verda Inference (Kimi K3.1 Pro, DeepSeek V4.1 Flash): any published vision results.
- Cost per image at current prices for the models that look good.
- Adjacent fields: image-to-markup tasks that already work: chart to table (DePlot, MatCha and later), table
  image to HTML, formula image to LaTeX, molecule image to SMILES, sheet music to notation, screenshot to code
  (Design2Code): what model size and how much data did they need? GUI grounding (ScreenSpot-style benchmarks,
  OS-Atlas, UGround, ShowUI and newer): finding tiny icons on a large screen is our tiny-symbol problem, and those
  models are small and open. Remote-sensing vision-language models that count objects; chart and diagram question
  answering (ChartQA, AI2D); map question answering.
- Answer: is "detector proposes, small model verifies marks" shown to beat either alone? Is a fine-tuned 0.2-3B
  model competitive with a detector on counting?

## L8 `lit-data`: data, pretraining, synthetic
- Datasets with licences and exact contents: CubiCasa5K, FloorPlanCAD, ArchCAD-400K (if it exists), R2V, RPLAN,
  ROBIN, CVC-FP, SESYD, MLSTRUCT-FP, MSD (Modified Swiss Dwellings), ResPlan, WAFFLE, Structured3D, ZInD. For each:
  does it overlap CubiCasa5K, can it be used commercially, does it have symbol boxes.
- Self-supervised pretraining for line drawings and documents (DiT, MAE and DINO on documents, DINOv2/DINOv3 as a
  frozen backbone for detection on drawings); evidence on small-data fine-tuning vs from scratch.
- Synthetic floor plans: rendering vector plans in randomised styles, symbol copy-paste, generative floor-plan
  models as a data source; degradation augmentation (Augraphy and similar); sim-to-real gap numbers.
- Domain adaptation between drawing styles (clean CAD render to scan).
- Tudor's stoa-data report covered part of this (ResPlan, Roboflow sets): ask the orchestrator for it first and do
  not repeat it.
- Adjacent fields: fields that train mostly on rendered data and measured the gap to real images: scene-text
  and document OCR (SynthText-style generators, synthetic documents), optical music recognition (rendered scores to
  scanned scores), chart and table recognition, PCB and circuit datasets, historical map style transfer, domain
  randomisation in robotics. Look for which randomisations mattered (line weight, fonts, noise, paper texture,
  scanning artefacts) and for cheap real-data mixing ratios.
- Answer: what is the best commercial-safe training set we could assemble in a night, and how much does synthetic
  data help in papers that measured it?

## L9 `lit-sheet`: normalisation and sheet layout
- Page and text orientation classifiers, deskew, dewarp for photographed documents (2024-2026), with licences.
- Splitting a sheet into views or plans: layout analysis for architectural sheets, title-block detection, view
  classification (plan, section, elevation), multi-plan separation.
- Upscaling for OCR and detection: what is shown to help or to hurt (invented strokes).
- Image quality gating: predicting "too small or too degraded to read" before answering.
- Tudor's stoa-hardimg report covered orientation, binarisation, SAHI and augmentation: ask the orchestrator for it
  first and extend it, mainly on sheet splitting and quality gating.
- Adjacent fields: compound-figure separation in scientific papers (splitting one image into its sub-panels is
  our "several plans on one sheet"), comic panel extraction, newspaper and magazine article segmentation, document
  layout analysis (DocLayNet-style models), map sheet layout (map body, legend, inset), receipt and ID-document
  orientation and cropping, document image quality assessment, capture-quality gating for fingerprints and ID
  photos. Look for orientation methods that work from structure when there is little text.
- Answer: a proven orientation method for plans with almost no text; a method for counting plans on a sheet.

## L10 `lit-trust`: confidence, abstention, verification
- Calibration of object detectors and of counts; conformal prediction for detection and counting; selective
  prediction and risk-coverage curves.
- Uncertainty from test-time augmentation and ensembles; weighted box fusion.
- Consistency constraints as error detectors (domain rules across predicted quantities).
- Out-of-distribution detection for document images (is this a floor plan at all).
- Human-in-the-loop verification of counts: how takeoff tools and annotation tools present marks for fast review;
  measured review-time savings.
- Adjacent fields: fields that already run "machine answers, person checks the doubtful ones": invoice and
  form extraction (straight-through-processing thresholds), double-key data entry, medical image reading with
  selective referral, cell-count quality control, perception calibration in driving, label aggregation from
  several noisy annotators (Dawid-Skene and successors, for combining our methods), N-version software, and
  election audits (risk-limiting audits: how few items a person must check to certify a count, which maps onto
  "how many marks must the surveyor check"). Look for guarantees that can be stated in one sentence.
- Answer: the cheapest confidence signal with published evidence that it ranks right above wrong for counts; how to
  state a guarantee ("90% of answers we mark sure are right") honestly.

## L11 `lit-vector`: raster to vector, structural and classical routes
- Line-segment and wireframe detectors: LSD, M-LSD, HAWP v2/v3, LETR, DeepLSD, ScaleLSD; junction detection.
- Deep vectorisation of technical drawings; raster-to-CAD.
- Structural floor-plan analysis: walls first, openings as gaps in walls, door arcs, classical symbol spotting (graph
  matching, SESYD-era methods) and how they compare with learned detectors in papers that tested both.
- Symbol spotting on vector primitives (FloorPlanCAD: CADTransformer, GAT-CADNet, SymPoint, SymPoint-V2,
  CADSpotting, VecFormer): can any take vectorised raster as input, with what loss?
- Adjacent fields: historical and cadastral map vectorisation, road-network extraction from aerial images,
  vector HD-map construction, PCB trace extraction and reverse engineering, circuit schematic to netlist, sketch and
  line-art vectorisation and clean-up (animation, design), font and logo vectorisation, mechanical drawing
  vectorisation, staff-line removal in sheet music (separating symbols from the lines they sit on), flowchart and
  graph recognition. Look for topology-preserving methods and for results on noisy scans, not clean renders.
- Answer: is there any evidence a vectorise-then-rules route beats direct detection on scanned plans?

## L12 `lit-market`: products, BIM route, what a judge has seen before
- Products that read floor plans or do AI takeoff: Togal.AI, Kreo, Bluebeam Max, Autodesk Takeoff, Make a BIM,
  WiseBIM, SWAPP, CubiCasa's own product, others. Published accuracy, how they show evidence, pricing per sheet.
- Scan-to-BIM and 2D-to-IFC research; open tools.
- Question-answering over drawings: datasets and benchmarks in construction (drawing QA, BIM QA, IFC-Bench).
- Stoa's own public material on drawing reading, if any.
- Adjacent fields: products that sell machine measurement from images with stated accuracy and a review step:
  roof and property measurement from aerial imagery (EagleView, Hover), floor plans from phone scans (CubiCasa's
  app, Matterport, Zillow), instant quoting from mechanical drawings (Werk24, Xometry), invoice and document
  processing platforms, mapping and GIS digitisation services, AI reading aids in radiology and pathology. How do
  they state accuracy, price per item, show evidence, and handle "not sure"? Which of those patterns has
  construction takeoff not adopted yet?
- Answer: what would be new to a construction-AI CTO, and which claims (accuracy, cost per sheet) are the
  yardsticks our numbers will be compared with?

