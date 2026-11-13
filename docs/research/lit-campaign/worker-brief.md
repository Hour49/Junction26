# Worker brief: literature campaign, image to extraction_v1

You are one of 12 read-only research agents. Your scope is one section of [scopes.md](scopes.md); your orchestrator
tells you which. Read this file, then your scope, then start.

## The problem

CubiCasa raster floor plans are 67.3% of Stoa's questions, and all of them are counts scored exact. The dataset
answers are CubiCasa5K annotation counts. Given a correct `extraction_v1` JSON
([record 0004](../../decisions/0004-extraction-format.md)) our counting rules reproduce the answers, so the open
problem is getting from the PNG to that JSON:

- `elements`: window (one per drawn cell), door, toilet, sink, shower, bathtub, sauna stove. A plan has about 9
  windows and 9 doors; symbols are 5 to 20 px on many images.
- `rooms`: outline, type and raw label. The type follows the printed Finnish label (MH, OH, K, KH, PH, WC, S,
  PARV...); a bedroom with no label counts as 0.
- `plans`: how many plans the sheet shows. One sheet in five has several, and the answers sum them.
- `scale` and room areas: printed areas, dimension lines, scale text or bar, a "not to scale" note, or an estimate
  that says it is one.
- The images: median longest side 855 px (minimum 240), about one in three rotated by 90 or 180 degrees, scans and
  phone photos among them.
- The number to beat is the most common answer per question type: 55.3% overall, 13.2% on windows, 11.6% on doors
  (dev split). Measured so far: the CubiCasa authors' 2019 weights 53.1%, a count-only network 59.3%.
- For training we have about 104k symbol boxes, room polygons with labels and an approximate scale for 3,828 dev
  images ([record 0003](../../decisions/0003-training-data.md)). Hardware: one 12 GB and one 16 GB GPU, more by the
  hour.
- Whatever we pick has to train and run by Saturday 14 Nov 22:00 (Helsinki).

## Tools

- arXiv: the `arxiv` MCP server where it is installed (`mcp__arxiv__search_papers`, `download_paper`, `read_paper`,
  `get_paper_outline`, `read_paper_section`, and a citation graph; load them with ToolSearch "arxiv"). It returns
  full text, and downloaded papers are cached in `~/.cache/arxiv-mcp/papers` for every agent on the machine. Use the
  citation graph to walk forward from a known paper to 2025 and 2026 work.
- Web search and fetch for venues, GitHub, Papers with Code, Hugging Face model cards and product pages.
- A headless browser (Playwright MCP) where it is installed, for public pages that refuse a plain fetch. Owner
  decision, Bogdan, 2026-11-13: "you can use masked headers". That covers browser headers on public pages. It does
  not cover logging in, creating accounts, solving captchas or reading paywalled content. Load one page at a time,
  and if a site still refuses, use another source.
- A tool that is missing on your machine is not a blocker: say so in the report and use what you have.

## Rules

- Read-only. No code in the repo, no datasets or weights downloaded, no paid APIs, no drawing uploaded anywhere.
  Never use the board, never message other agents, never ask the human: questions go in your report.
- Open the paper or the repo before you cite it. Nothing from memory. Every claim carries its source (URL and the
  date you read it) and is marked verified (you read it there) or reported (the authors' own claim).
- Look for 2025 and 2026 work on purpose: arXiv by date, the citation graph, CVPR, ICCV, ECCV, NeurIPS, ICDAR and
  WACV of those years, GitHub sorted by last push.
- Look sideways (Bogdan, 2026-11-13: "look for similar concepts which might traslate well to our use case"). Floor
  plans are a small field, and the same problem has often been solved better somewhere else. Spend about a third of
  your time on the adjacent fields in your scope, and add any field you find where the problem has the same shape:
  small repeated symbols on line art, sparse rotated text, exact counts, thin-line structure, a ruler that
  calibrates pixels, a person checking a machine's marks. For each transfer candidate write the field and the task,
  what plays the role of our object there (a note head for a window cell, say), why it should transfer, what would
  break on our images, and whether the code and weights work as they are, need fine-tuning on our boxes, or only
  give the idea. A transfer with measured results and usable code ranks above a floor-plan paper with neither.
- For each candidate method record: what it is, in two lines; year and venue; code URL and licence; weights URL and
  licence; training data; the metric and benchmark it reports; input size and GPU memory to train and to run; hours
  to a first number on our data (your estimate, marked as one); the JSON field it would fill; and a verdict of try,
  maybe or skip with one reason.
- Licences: shipped code must be MIT, BSD, Apache-2.0, ISC or unmodified LGPL
  ([record 0006](../../decisions/0006-lgpl-dependencies.md)). AGPL and GPL are out, which rules out Ultralytics
  YOLO, PyMuPDF and Surya. Non-commercial data or weights may be used for local training only and are never shipped
  (record 0003).
- Leakage: 829 of our 959 sealed eval drawings are in CubiCasa5K's train split. Weights trained on CubiCasa5K, or
  on a repackage of it (many Roboflow floor-plan sets are), cannot be used for scored runs. Flag every such
  checkpoint.
- Exact count is the metric. Prefer work that reports counting accuracy, per-class AP on small objects, or results
  on CubiCasa5K, R2V, RPLAN or FloorPlanCAD. A method shown only in figures is a "maybe" at best.

## Report

60 minutes, then write `.agents/research/lit-<name>.md` (local; your orchestrator publishes it after review):

1. Top 5, ranked, floor-plan work and transfers in one list, each with its verdict line and source.
2. The full table, with a column saying whether the method is from our field or which field it transfers from.
3. From other fields: the transfer notes.
4. Looked for and did not find.
5. Open questions, and which tools were missing.

End with a short last message: the report path and your top 3 in three lines.
