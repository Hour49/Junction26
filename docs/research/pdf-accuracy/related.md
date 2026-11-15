# Related work that carries over: schedules, legends, cross-sheet links, room names, commercial tools, VLM benchmarks, self-checks

Worker "related", 2026-11-15. Brief: `BRIEF.md`. Builds on `docs/research/lit-campaign/` (ideas #31, #181, #317,
#337, #351, #461 already cover parts of this; not repeated) and on what the backend already does
(`backend/app/adapters/pdf_tables/`: lattice schedules from vector rulings, door/window/room schedule-vs-tag
checks; `app/core/pipeline/printed.py`: printed scale and printed counts as a second value).

## Summary

1. The cheapest accuracy is reading what the sheet already prints: frontier VLMs read text on drawings at 0.70-0.95
   but count doors/windows at 0.09-0.39 exact (AECV-Bench, 120 plans); our "48 DORMS" and 26,562 SF misses are this.
2. ADOPT NOW: a printed area total (area table, "GROSS ... SF") becomes a second value of the total-area answer, the
   way `printed.py` already does for counts, plus a net-to-gross plausibility band (sum of rooms / printed gross
   outside about 0.6-1.0 = disputed, not answered as sure). Our 45% case falls outside it.
3. Room names: Vellum's own held-out test of counting by a plain printed noun scored 5/16 (31%), so no blind fuzzy
   match; NEXT is an English head-noun rule ("Secondary Classroom (Severe Needs)" is a classroom, "Classroom Storage"
   is not) that answers with the matched labels listed, behind a pre-registered line. rapidfuzz only for OCR typos.
4. Schedules on raster/borderless pages: img2table (MIT, now on pypdfium2, RapidOCR backend) is the only drop-in
   candidate; no measured number on drawing schedules exists anywhere (best public: a vendor blog, 20 door/window
   schedules, Gemini 2.5 Pro best, GPT-4o 38%). Table Transformer is trained on papers: SKIP. NEXT.
5. Commercial takeoff tools publish no verifiable accuracy (Togal "up to 98%", Kreo "94%" are vendor-only; the one
   independent Togal study: 11/13 count items exact after user correction); they get accuracy from human review,
   which supports our "show the evidence, say I don't know" stance rather than any technique to copy.

## Ranked findings

| # | Finding | Verdict | Number (dataset) | Licence | Effort |
| --- | --- | --- | --- | --- | --- |
| 1 | Printed area total / area table as second value of the total-area answer | ADOPT NOW | Tudor QA r4: we answer ~45% of a printed 26,562 SF; AECV-Bench OCR 0.70-0.95 vs door count 0.09-0.39 | n/a (own code) | S |
| 2 | Net-to-gross plausibility band on summed room areas | ADOPT NOW | Grossing factor 1.40 for K-8 schools (NJ DOE) = 0.71; offices 0.60-0.82; our 0.45 case flags. No floor-plan-extraction study measures it | n/a | S |
| 3 | Printed count vs counted (sheet total "48 DORMS"): extend the existing `printed_total` second value to vector pages | ADOPT NOW if not already reached on vector | Tudor QA r4: 40 vs printed 48 | n/a | S |
| 4 | Head-noun room-name match, answer with matched labels listed | NEXT | Vellum P1 (plain-noun counting) 5/16 = 31% held-out, line 40% (EXPERIMENTS.md); ISARC 2019 name-only room classifier 85.9% (Korean schools) | rapidfuzz MIT (typos only) | S-M |
| 5 | img2table for borderless and raster schedules | NEXT | No number on drawings; vendor blog: 20 door/window schedules, Gemini 2.5 Pro 79% on the hardest table, AWS 67%, Azure 55%, GPT-4o 38% avg | MIT (deps numpy, pypdfium2, opencv-contrib, bs4, xlsxwriter) | M |
| 6 | Cross-sheet links: sheet index + callout "detail/sheet" pairs to join plans with schedules | NEXT | No measured number; patents + ISI 2018 callout paper only | n/a | M |
| 7 | Legend-informed symbol recognition (legend entry as the class exemplar) | NEXT (research) | ">80%" across drawing styles (Springer 2025, abstract only, not floor plans); lit-campaign #181: template matching 0.58 on floor-plan blocks | unknown | L |
| 8 | VLM as the reader of tables/totals, not the counter | context | AECV-Bench: Gemini 3 Pro mean 0.51 (doors 0.39, windows 0.34, bedrooms 0.89, toilets 0.82); Claude Opus 4.5 0.42 (0.16/0.16/0.91/0.76). ArchSIBench: Gemini-3-Pro 77.9, Claude-Opus-4.6 53.3, humans 85.1-89.2 | AECV code on GitHub (licence not shown) | n/a |
| 9 | Commercial takeoff tools' accuracy claims | context / SKIP as a technique | Togal "up to 98%" (vendor), Kreo 94% (vendor), STACK/Bluebeam/Autodesk/PlanSwift none; Utica ASC 2026: 11/13 count items exact after user correction | closed | n/a |
| 10 | Microsoft Table Transformer (TATR) | SKIP | No number on drawing schedules; trained on PubTables-1M (scientific papers) and FinTabNet | MIT code and weights | M |
| 11 | Camelot / pdfplumber for vector tables | SKIP | Camelot 73.0 vs pdfplumber 40.4 on PDF tables (arXiv 1911.10683, not drawings); we already have a lattice reader on pdfium | MIT | M |
| 12 | Self-consistency of one model's repeated samples as confidence | SKIP (already ruled out, lit-campaign #317) | 48% of high-agreement answers wrong (2607.08065) | n/a | n/a |

## 1. Printed area totals as a second value (ADOPT NOW, S)

- What: when a sheet prints an area table or a total ("TOTAL 26,562 SF", "GROSS FLOOR AREA", "BRA 1 234 m²"), the
  total-area answer carries it as a second value with method `printed_total`, exactly as `printed.py` already does
  for printed counts. No rule decides: a difference beyond tolerance is a conflict for a person, and the answer
  is not "sure".
- Why it carries over: AECV-Bench (arXiv 2601.04819, Tables 1-2 and Fig. 6, read in the PDF) finds the gradient
  every reader of ours shows: text-centric QA 0.70-0.95, spatial 0.6-0.77, symbol counting worst. Printed numbers
  are the reliable modality; the takeoff is the unreliable one. Tudor's QA round 4: the sheet prints a 26,562 SF
  area table and we answer about 45% of it.
- Number: our own case above; no published study of "printed total vs measured" on floor plans was found.
- Plug in: vector pages: the area table is already a `Table` when ruled (`pdf_tables/lattice.py`); a row/title with
  "total|gross|net|sum" and a unit (SF, sq ft, m², m2) gives the value. Raster: the Carbon reader's
  `printed_facts` gets an `area_total` kind. `answering/tables.py` already sums a column; the missing piece is
  feeding that value into the area answer's conflict entry. Effort S. Test: a fixture sheet with a printed total
  and rooms summing to 45% of it must come back disputed with both values.

## 2. Net-to-gross plausibility band (ADOPT NOW, S)

- What: sum of measured room areas / printed gross area. Below about 0.6 or above 1.0 (plus measurement slack),
  the area answer is disputed ("the rooms I measured cover 45% of the 26,562 SF the sheet prints"). Inside the
  band it is no proof, only no alarm.
- Number: buildings' net-to-gross ratios: K-8 school grossing factor 1.40 (NJ DOE facilities efficiency standards)
  = 0.71 assignable; offices 0.60-0.82 (study guides, secondary). Assignable area excludes corridors, so the sum of
  all room polygons should sit above these. iGUIDE notes room lists don't add up to the total (minor rooms not
  itemised, rounding): so the band only flags, never corrects. No floor-plan extraction paper measures this check.
  Lit-campaign #337 (roomgraph, MIT) warns per room above 3% when a room prints its own area; this is the sheet-level
  counterpart.
- Plug in: one function in `core/pipeline` next to `second_count`, constants `NET_TO_GROSS = (0.6, 1.02)` with a
  one-line why. Pre-register the band on dev before shipping (it must not flag the Swiss vector sheets that score
  20/20). Effort S.

## 3. Printed counts on vector sheets (ADOPT NOW if missing, S)

- What: "SECOND FLOOR = 48 DORMS" against 40 counted bedrooms. `printed.py` reads printed facts on raster pages via
  Carbon; check whether vector pages' text reaches the same `printed_total` path. If not, the vector text layer is
  free and exact: a regex `(\d+)\s+(DORMS?|BEDROOMS?|UNITS?|ROOMS?)` over page text objects feeds it.
- Number: Tudor QA r4, 40 vs 48. Effort S (reuse the printed-fact model).

## 4. Room names: head-noun match with the labels listed (NEXT, S-M)

- Problem: "how many classrooms" against "Secondary Classroom (Severe Needs)" is refused. Today
  `review/ask.py::_noun_refusal` already names the labels that hold the noun (R3-A4) but never counts.
- Evidence against blind fuzzy matching: Vellum's own held-out test of counting rooms by a plain printed noun (P1,
  `docs/EXPERIMENTS.md` 15.4, PR #388) scored 5 of 16 (31%, line 40%) and was dropped. ISARC 2019 (Song, Kim, Lee:
  word embeddings on IFC space names of Korean schools) reaches 85.9% name-only: one in seven wrong, too low for a
  sure answer. No paper gives a calibrated refusal threshold for room-name matching.
- What carries over: English compounds are right-headed. Take the label without parentheses and numbers; its last
  noun is the head. "Secondary Classroom (Severe Needs)" has head "classroom" and matches; "Classroom Storage" has
  head "storage" and does not; "Bedroom" vs "bed" is not a head match. When every label whose head matches is
  counted, the answer says it: "14 rooms whose name ends in classroom: Secondary Classroom (Severe Needs) 3,
  Classroom 11", status not "sure" until a person accepts the grouping. Safe refusal stays when matched heads
  differ only by a modifier list we can't read, or when a label holds the noun as a modifier only.
- Typos and OCR: rapidfuzz (MIT, C++ backed) `fuzz.ratio >= 90` against the drawing's own label set only (closed
  set, as lit-campaign #193 says for OCR), and only when the second-best label scores at least 10 below. These two
  numbers are a starting guess, not measured: pre-register them on dev.
- Plug in: `core/answering/answer.py::noun_forms` gains the head rule; `_noun_refusal` turns its "holding" branch
  into an answer with the list when all holding labels are head matches. Gate: rerun the P1 held-out 16 plus golden
  0/3,058 regressions; line set before the run. Effort S (rule) to M (with the gate).

## 5. Schedules on raster and borderless pages: img2table (NEXT, M)

- What: our lattice reader needs vector rulings. A scanned or rasterised schedule, or a borderless area table, gives
  nothing. img2table (github.com/xavctn/img2table) finds tables in images and PDFs with OpenCV, has
  `borderless_tables=True`, and takes RapidOCR (already our dependency) as its OCR.
- Licence: MIT. Dependencies checked in its `pyproject.toml` today: numpy, pypdfium2, opencv-contrib-python (Apache
  2.0), beautifulsoup4, xlsxwriter. No PyMuPDF (older releases used it; pin a current one).
- Number: none on drawing schedules. The only public door/window-schedule comparison is a vendor blog (BusinessWare,
  18 drawings, 20 schedules, 7x3 to 38x18 cells, metric = correct cells / all cells): hardest table Gemini 79.17%,
  AWS Textract 66.67%, Azure Layout 55.00%; GPT-4o 38.41% average; Google Layout Parser did not detect them as
  tables; more resolution and prompting did not help GPT-4o. Treat as indicative only.
- Plug in: a `raster_tables` adapter returning `drawing.model.Table`, so `answering/tables.py` and the schedule
  checks work unchanged. Measure on our raster schedule pages first (cell accuracy against a hand-typed copy of 3-5
  tables). Effort M.

## 6. Cross-sheet references (NEXT, M)

- What: a set's sheet index (G-001) lists sheet numbers and titles; callouts are a circle split in two (detail number
  over sheet number, e.g. 3/A-501); "SEE A-501" in notes. Linking them tells which schedule belongs to which plan in
  a multi-file set, and catches a schedule sheet that is missing (the plan says A-601, the set has none).
- Evidence: no measured number found. Patents "Error identification, indexing and linking construction documents"
  (US 9,710,519 and family) describe index-vs-files, unreferenced details and broken links; ISI Kolkata 2018 detects
  circular callouts; Trimble ProjectSight normalises A-1/A1/A.1/A 1. AECV-Bench lists "mismatched callouts" as a
  QA/QC use case, not a measured task.
- Plug in: vector text only first: sheet numbers from title blocks (`^[A-Z]{1,2}-?\d{1,3}(\.\d{1,2})?$`, already
  excluded as tags in `pdf_tables/tags.py`), joined with `PdfSet` pages. Effort M; worth it only when multi-file
  uploads are in scope.

## 7. Legends to map symbols to meaning (NEXT, research)

- Our state: `answering/tables.py` already reads key/legend tables for what a code means (finish keys, keynotes)
  and never counts them. Symbol legends (a drawn symbol next to a word) are not read.
- Evidence: "Legend-Informed Symbol Recognition" (Springer 2025) uses each legend entry as a contrastive exemplar,
  >80% classification across drawing styles (abstract; not floor plans; full text not read). A YOLO11x
  blueprint-legend-layout detector on Hugging Face reports mAP50 0.964 for legend symbols on 30 validation images
  (licence of Ultralytics weights is AGPL: research only). Lit-campaign #181 already found template matching from
  a legend at 0.58 on floor-plan blocks: do not try.
- Verdict: no number on our kind of data; L effort. Legend cut-off before counting (#31) stays the useful part.

## 8. VLM benchmarks on drawings (context for where to use a VLM)

- AECV-Bench (Kondratenko et al., arXiv 2601.04819, Jan 2026; 120 floor plans counting, 192 QA pairs). Exact-match
  counting, Table 1: Gemini 3 Pro mean 0.51 (door 0.39, window 0.34, bedroom 0.89, toilet 0.82); GPT-5.2 0.49
  (0.28/0.27/0.91/0.76); Claude Opus 4.5 0.42 (0.16/0.16/0.91/0.76); best open GLM-4.6V 0.39; Qwen3-VL-8B 0.39.
  MAPE: Gemini 16.0% mean, doors 15.0%, windows 20.4%. QA: OCR 0.70-0.95, spatial 0.6-0.77, counting worst.
  Authors' advice: counting "as assistive tools that surface candidates and uncertainty". Code/data on GitHub
  (AECFoundry/AECV-Bench), licence file not shown.
- ArchSIBench (arXiv 2605.20837, May 2026; 3,000 multiple-choice items, 17 subtasks, floor plans among others):
  Gemini-3-Pro 77.9, GPT-5-mini 62.8, Claude-Opus-4.6 53.3, Claude-Opus-4.5 49.1; humans 85.1 (no architecture
  training) and 89.2 (trained). Multiple choice, not counts or areas.
- FloorplanQA (arXiv 2507.07644): text LLMs on symbolic floor plans, not images: not comparable.
- Use for Vellum: a VLM is a good reader of printed totals, schedules and labels (findings 1, 3, 5) and a bad
  counter; this matches the shipped design and argues for spending VLM calls on text regions.

## 9. Commercial takeoff tools: how they get accuracy, what they claim (context)

- Togal.AI: "up to 98% accuracy" on its homepage; the "independent study" cited in its blog is not linked. Help
  centre: room areas (net, and gross from wall centrelines) as "a fast starting point" users "review and edit". PDF
  only, no native CAD. Independent: Utica (ASC 2026), one commercial building: 11/13 count items exact after the
  user corrected markups; door types -9.09% and +66.67%; areas under-estimated (lit-campaign #461).
- Kreo: 94% outline accuracy for Auto Measure 3.0 (Kreo's own figure, via a third-party blog), a model-internal
  "second review pass"; reviewers say "hit and miss" on dense or scanned sheets.
- STACK: AI for setup (scale detection, page naming, one-sheet symbol counts); no accuracy figure.
- Bluebeam: VisualSearch/Auto-Count find repeated symbols; Max AI reviews markups; no accuracy figure. Its blog poses
  the schedule-vs-plan check ("Does every door listed in this schedule exist in the plan?") as an AI use case.
- Autodesk Takeoff, PlanSwift/On-Screen Takeoff (ConstructConnect), Procore: speed figures only ("up to 95% faster",
  "five pages in about 30 seconds each"); ConstructConnect lists low-res scans, unusual symbols and revisions
  across sheets as where AI needs review.
- Take-away: none publishes a held-out accuracy; all rely on vector PDFs, a person checking, and schedule
  cross-checks. Vellum's dev/eval split numbers are already stronger evidence than any vendor's. Nothing to adopt
  as a technique.

## 10-12. Skipped

- Table Transformer (github.com/microsoft/table-transformer; MIT code, MIT weights on HF `bsmock/TATR-v1.1-Pub`):
  trained on PubTables-1M (scientific articles) and FinTabNet; no number on drawing schedules; needs a GPU or slow
  CPU DETR plus our own OCR; our vector lattice reader already covers ruled schedules. SKIP.
- Camelot / pdfplumber (MIT): Camelot 73.0 vs pdfplumber 40.4 on PDF tables (Zhong et al., arXiv 1911.10683, not
  drawings). Our lattice reader is tuned to Revit stacked blocks and title rows; a second vector table library adds
  a dependency for what we have. SKIP; pdfplumber's text strategy is a fallback idea only for borderless vector
  area tables if finding 1 shows they exist.
- Self-consistency of repeated VLM samples: already ruled out (lit-campaign #317). Cross-source checks (printed vs
  counted, schedule vs tags, net-to-gross) are the independent checks to use instead.

## Sources

- AECV-Bench: https://arxiv.org/abs/2601.04819 (PDF read, Tables 1-2, sections 4.1-4.2); https://github.com/AECFoundry/AECV-Bench
- ArchSIBench: https://arxiv.org/abs/2605.20837 ; https://huggingface.co/papers/2605.20837
- FloorplanQA: https://arxiv.org/abs/2507.07644
- Door/window schedule extraction benchmark (vendor blog): https://dev.to/businessware/benchmark-how-well-ai-models-handle-table-processing-29kl
- img2table: https://github.com/xavctn/img2table (LICENSE and pyproject.toml checked)
- Table Transformer: https://github.com/microsoft/table-transformer ; https://huggingface.co/bsmock/TATR-v1.1-Pub
- Camelot comparison and arXiv 1911.10683: https://camelot-py.readthedocs.io/en/latest/user/comparison.html ; https://arxiv.org/pdf/1911.10683
- Room-name classification: https://www.iaarc.org/publications/2019_proceedings_of_the_36th_isarc/spatial_information_enrichment_using_nlp_based_classification_of_space_objects_for_school_bldgs_in_korea.html
- Net-to-gross: https://www.nj.gov/education/facilities/lrfp/fes.pdf ; https://open-exam-prep.com/study-guides/are-pa/ch11-space-standards-area/nsf-gsf-efficiency ; https://help.youriguide.com/support-center/floorplans-and-measurements/information/question-about-room-dimensions-and-floor-areas
- Cross-sheet references: https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9710519 ; https://digitalcommons.isical.ac.in/conf-articles/130 ; https://projectsight.trimble.com/?p=1100
- Legends: https://api.crossref.org/works/10.1007%2F978-3-662-72243-5_23 ; https://huggingface.co/GreenMap/yolo11x-blueprint-legend-layout-detector
- Togal: https://www.togal.ai/ ; https://help.togal.ai/en/articles/15602901-ai-powered-area-and-wall-detection ; https://togal.ai/blog/ai-blueprint-reading-accuracy ; Utica study https://easychair.org/publications/paper/pkrRp
- Kreo / STACK: https://www.kreo.net/news-2d-takeoff/how-does-artificial-intelligence-work-in-kreo ; https://www.stackct.com/floor-plan-ai/
- Bluebeam: https://blog.bluebeam.com/why-construction-ai-needs-drawing-intelligence-2/
- ConstructConnect: https://www.constructconnect.com/blog/are-ai-takeoffs-accurate-in-2026
- Vellum internal: `docs/EXPERIMENTS.md` 15.4 (P1 5/16), `backend/app/core/review/ask.py::_noun_refusal`, `backend/app/core/pipeline/printed.py`, `backend/app/adapters/pdf_tables/`
