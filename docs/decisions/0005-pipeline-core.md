# 0005: The backend pipeline is ports and adapters: a pure core, one adapter per port, one composition root

- Status: accepted
- Date: 2026-11-13 23:18 (Europe/Helsinki)
- Decided by: Bogdan for the shape ("make sure this will use the core nd composition of the pipeline", "Make sure
  it's strucutred well im modules, and it has a hello world of the pipeline and we can run the golden set now for
  example and get a 0 or very low score", "also make sure to use ports and adapters"); the module map by agent core
  (worker), approved by Bogdan's orchestrator on 2026-11-13 23:24 after review
- Board thread: #15

## Context

[PIPELINE.md](../PIPELINE.md) has ten ingest stages and four routes, and several owners will build them in parallel
this weekend. The formats on both ends are fixed ([0002](0002-answer-format.md) answer_v1,
[0004](0004-extraction-format.md) extraction_v1) and `eval/` scores them. What was missing is the code between them:
a pipeline that already runs end to end, so that each feature replaces one piece and its effect shows in the next
scored run.

## Decision

`backend/app` has a pure core that declares its ports as `typing.Protocol`, adapters that implement them, and one
composition root. Every stage exists today with a do-nothing ("hello world") implementation.

```text
app/core/drawing/model.py     the drawing model (Drawing, Page, Scale, Plan, Element, Room, Table, Conflict)
app/core/pipeline/            ingest: one module per stage, ingest.py runs them, ports.py, model.py
app/core/answering/           question -> query -> lookup in the takeoff: answer.py, ports.py, model.py
app/adapters/                 dataset_files, page_sizes, hello, extraction_v1, answer_v1, golden_dir, vector_pdf/
app/composition.py            build_pipeline(settings, dataset) -> Pipeline, the only place adapters are chosen
app/cli.py                    python -m app.cli golden ...   (API routes come later and use the same Pipeline)
```

| Stage (module in `core/pipeline/`) | Hello world today | Becomes real by |
| --- | --- | --- |
| 1-2 `inventory` | size and sha256 per file | a store of drawings by hash; unpacking archives |
| 3 `identify` | format from the first bytes; unknown content is set aside | telling non-drawings apart |
| 4 `group` | same folder and name, any extension | IFC model with its sheets |
| 5 `route` | richest format in the group: bim, cad, vector, raster | telling a scanned PDF from a drawn one |
| 6 `normalise` | pages as the file gives them | rotation; rendering |
| 7 `extract` | calls the route's `Extractor`; `hello` reads nothing, scale `no_scale`. Vector route: `pdf` reads drawn PDFs (2026-11-13) | one adapter per route |
| 8 `second_count` | pairs two methods' values into `conflicts` and applies the resolution rules of PIPELINE.md §2; `pdf` brings the scale bar, the scale text and the printed room areas of a drawn PDF (2026-11-14); `hello` measures nothing | room, storey and element counts from a second source (the IFC model) |
| 9 `rules` | one rule: every listed item counts once | the dataset's conventions as `CountingRule`s |
| 10 `takeoff` | a count per element class, room type and plan, with marks | areas, lengths, volumes |

Ports (`core/pipeline/ports.py`, `core/answering/ports.py`) and their adapters:

| Port | What core asks of it | Adapter today |
| --- | --- | --- |
| `DrawingFiles` | bytes of a file by its dataset path | `DatasetFiles` (folder on disk, refuses paths that leave it) |
| `PageReader` | page sizes of a sheet, as rendered | `PageSizes` (pypdfium2, Pillow) |
| `Extractor`, one per route | what it read from the group's richest source, as page fractions of the sheet | `HelloExtractor`; vector: `PdfVectorExtractor` (`EXTRACTOR_VECTOR=pdf`) |
| `SecondCounter` | an independent second measurement | `PdfSecondCounter` (`SECOND_COUNTER=pdf`); `HelloSecondCounter` |
| `DrawingSink` / `DrawingSource` | store and load a drawing model | `ExtractionV1Writer` / `ExtractionV1Reader` |
| `QuestionParser` | question text to a `Query`, or `Unsupported` | `HelloParser` |
| `AnswerSink` | take an answer | `AnswerV1Writer` |
| `Clock` | seconds, for latency | `time.perf_counter` |

- To plug in an extractor, second counter or parser: write the adapter in `app/adapters/`, add its name to the
  port's `Literal` in `app/settings.py` (and `.env.example`), add a `case` in `app/composition.py`. Core and the
  entry points don't change. The setting then picks it (a vector reader named `pdf` would be `EXTRACTOR_VECTOR=pdf`).
- Each sheet file (PDF, PNG, JPEG) gets its own drawing model, as 0004 requires. A group has one route and one source: the
  PDF and the PNG of a swiss plan are both extracted from the PDF, each into its own page frame. An IFC or DXF file
  is a source to read from and never gets a drawing model of its own.
- The drawing model is a set of pydantic models that serialise as extraction_v1, so the adapter only adds
  `schema`, `split` and `truth`. It also carries `tables` and `conflicts` in the shapes pinned on 2026-11-13 (0004's
  amendment); the writer leaves out the one that is not set. `backend/tests/test_formats.py` validates what the
  writers produce against `eval/schemas/*.schema.json`.
- Answering is a lookup. `known_quantities(drawing)` runs stages 9-10 on a stored drawing; `answer_question`
  looks the query's quantity up. A question that can't be answered gets `answer: null` and `method:
  "refused:<why>"` (`no-drawing`, `unsupported-question`, `not-in-drawing`).
- The CLI and the API share the use cases. Both build a `Pipeline` with `build_pipeline` and call `Pipeline.ingest` and
  `Pipeline.answer_questions` (or `answer_question` for one question). Only the composition root imports adapters
  of pipeline ports; `tests/test_architecture.py` keeps core free of adapters, settings, the CLI and PDF or image
  libraries.

## Alternatives considered

- Stage classes with a common base and a runner: ENGINEERING.md §1 rules out base-class hierarchies; ten functions
  called in order in `ingest.py` are easier to read and test.
- Dataclasses in core plus a mapping layer to extraction_v1: twice the types for the same fields, and
  ENGINEERING.md §1 rules out DTO layers. pydantic is already a dependency and is not an outside service.
- One route per file instead of per group: a swiss PNG would go to the raster reader although the PDF of the same
  plan is next to it (requirement I4).
- Storing the takeoff in the extraction file: extraction_v1 has no place for the marks behind each quantity.
  Computing it from the stored lists costs no model call.
- A single `ports.py` for all of core: pipeline and answering types would import each other through it.

## Consequences

- A new feature is one adapter or one stage function, and its effect is the difference between two recorded runs.
  The floor is the `hello-world` run of 2026-11-13: Part 1 element F1 0.0%, count exact 27.7% (true zeros only),
  scale status right on the 10 `nothing` cases; Part 2 0 of 2,948 from both the pipeline's and the gold drawings.
- Differences from PIPELINE.md as drawn: the scale and the plans on a sheet come from the route's extractor
  (stage 7), not from stage 6, because the prototype reads the scale in the same pass as the rooms
  (`prototypes/pdf-extract/swiss_areas.py`).
- Not built yet: unpacking, reuse by hash, spotting non-drawings, IFC grouping, rendering, and a drawing model for
  a model file with no sheet.
- The vector route (`EXTRACTOR_VECTOR=pdf`, `app/adapters/vector_pdf/`, 2026-11-13) reads page 1 of a drawn PDF
  and nothing else: the scale from the sheet's text and scale bar, then the rules of the sheet style it recognises
  (swiss_dwellings plans; sheets IfcConvert rendered from an IFC model). A PNG of the same sheet gets the same
  fractions and its own metres per pixel. Recorded as `vector-pdf-v1`: swiss element F1 100%, rooms and areas 100%;
  ifc_models rooms and areas 100%, element F1 80.4%. Not built in it: columns, stairs, railings, slabs and beams
  on IFC-rendered sheets (the sheet draws columns like walls, so they are listed as walls, and the rest in one
  shared style), sheets in any other style (only their scale is read), pages after the first, SVG sources, and
  telling a scanned PDF from a drawn one (stage 5).
- Stage 8 on drawn PDFs (`SECOND_COUNTER=pdf`, 2026-11-14). The second counter re-reads the page and hands over
  the scale as the text prints it and as the bar measures it, and on swiss plans the area printed in each room
  under the extractor's room id. `second_count` adds the extraction's own side (element counts; each room's area,
  which an extractor measures as the outline at the sheet's scale) and lists every quantity with two methods.
  Resolution follows PIPELINE.md §2 and the drawing carries the resolved value: on a scale conflict the extractor
  takes the bar's value, so the areas use it; on a room-area conflict stage 8 puts the printed area on the room.
  An agreement changes nothing. Measured on the 879 dev sheets of the PDF sources: 6,547 room areas and 877
  scales compared, all agree (largest gaps 0.58% and 0.09%), so both conflict paths are held by synthetic tests
  only. Cost: each PDF is parsed a second time (ingest of those sheets 15.2 s to 25.9 s); a parsed-page cache by
  content hash would remove it and is not built.
- `read` (2026-11-14): every extractor says which element classes, and `room`, it looked for; the drawing and the
  extraction_v1 file carry it. `hello` and a PDF in no known style say `[]`, so none of their counts is a zero.
- Open with the formats: a count per room type has no `subject` kind in `conflicts`, so stage 8 compares element
  classes only. When answer_v1.1 lands, a refusal should set `abstain: true` with the reason in `explanation`, and
  the golden run should also answer `part2_answering/extras.jsonl`.
- The drawing model checks field ranges only. The cross-field rules of 0004 are checked by
  `stoa_eval validate-extraction`, and `score-extraction` refuses a file that breaks them.
- Revisit if a route needs more than one extractor per drawing, or if answering needs model calls at question time.
