# backend

The product pipeline: it reads drawing files into one drawing model per file, then answers quantity questions from
that model. Python 3.13, ports and adapters. The design is in
[docs/decisions/0005-pipeline-core.md](../docs/decisions/0005-pipeline-core.md), the stages in
[docs/PIPELINE.md](../docs/PIPELINE.md).

Every port started as a do-nothing "hello world" adapter: with all of them the pipeline runs end to end on the
golden set and scores near zero. Each real feature replaces one adapter or one stage, and the next scored run shows
what it gained. The table at the end says which parts are real today.

## Layout

```text
app/core/drawing/      the drawing model (serialises as extraction_v1)
app/core/pipeline/     ingest: one module per stage, ingest.py runs them, ports.py declares what they need
app/core/answering/    question -> query -> lookup in the drawing's takeoff
app/adapters/          implementations of the ports: files, page sizes, output formats, hello-world stand-ins
app/composition.py     picks the adapter of each port from the settings
app/cli.py             command line entry point
app/api/, app/main.py  FastAPI app (only /health so far)
```

Core never imports an adapter, the settings or a PDF or image library; `tests/test_architecture.py` checks it.

## Commands

```bash
uv sync --locked
./check.sh            # ruff, format, pyright, pytest, uv audit: what CI runs
./check.sh quick      # lint, format and types only
uv run uvicorn app.main:create_app --factory --reload
```

## Run the golden set and score it

The golden set (v2) and the dataset must be on disk first (`eval/README.md`, `data/README.md`). Each run needs a
new `--out` folder.

```bash
# 1. In backend/: ingest the Part 1 files and answer the Part 2 questions from the pipeline's own extraction
uv run python -m app.cli golden --golden-dir ../data/stoa/golden/v2 \
    --dataset ../data/stoa/full/junction-dataset --drawings pipeline --out ../data/stoa/runs/<name>

# 2. The same questions answered from the gold extraction, which takes reading errors out
uv run python -m app.cli golden --golden-dir ../data/stoa/golden/v2 \
    --dataset ../data/stoa/full/junction-dataset --drawings gold --out ../data/stoa/runs/<name>-gold

# 3. In eval/: score Part 1 (extraction), then Part 2 for both runs. Every scored run is recorded.
uv run python -m stoa_eval score-extraction ../data/stoa/runs/<name>/extraction --name <method>
uv run python -m stoa_eval score ../data/stoa/runs/<name>/answers.jsonl --name <method> --reads pipeline-extraction
uv run python -m stoa_eval score ../data/stoa/runs/<name>-gold/answers.jsonl --name <method> --reads gold-extraction
```

Step 1 writes `<out>/extraction/<source>/<file name>.json` (one extraction_v1 per drawing file), `<out>/ingest.json`
(what each stage did to each file) and `<out>/answers.jsonl` (one answer_v1 line per question). Step 2 writes only
`answers.jsonl`. Add `--no-record` to a scoring command for a scratch check that is not kept.

When the golden folder has `part2_answering/extras.jsonl` (reworded, unanswerable, estimate and conflict questions,
ids from 1000001), both steps answer those lines too, into the same `answers.jsonl`, and `score` reports them as
their own slices. Only a line's `id`, `path` and `question` are read: `answer`, `expect` and `why` are its answer key.

The hello-world floor that runs are compared against pins the do-nothing adapters, because the defaults are real
ones now:

```bash
EXTRACTOR_BIM=hello EXTRACTOR_VECTOR=hello SECOND_COUNTER=hello QUESTION_PARSER=hello \
    uv run python -m app.cli golden \
    --golden-dir ../data/stoa/golden/v2 --dataset ../data/stoa/full/junction-dataset --drawings pipeline \
    --out ../data/stoa/runs/hello-world
```

## Run any questions file

`answer` takes a questions file in the dataset's format (the dataset's `questions.jsonl`, or
`data/stoa/split/dev.jsonl`) instead of a golden folder. It ingests every drawing a question names once, answers
every question from it, and writes the same `extraction/`, `ingest.json` and `answers.jsonl`.

```bash
# In backend/: the whole dev split (101,651 questions on 4,735 files: 62 s, 1.6 GB on 2026-11-14 with the
# defaults, which read the 28 model files asked about; 48 s, 0.6 GB with EXTRACTOR_BIM=hello SECOND_COUNTER=pdf)
ANSWER_PRIOR=none uv run python -m app.cli answer --questions ../data/stoa/split/dev.jsonl \
    --dataset ../data/stoa/full/junction-dataset --out ../data/stoa/runs/<name>

# In eval/: score it against the dev split, as a scratch check
uv run python -m stoa_eval score ../data/stoa/runs/<name>/answers.jsonl --against dev --no-record
```

A line needs `path` and `question`. Its id is its `id` when it has one (the split's files do), else its line
number. The answer key on the line is never read. `ANSWER_PRIOR=none` matters on the dev split: the dev prior is
fit on these same questions, so it would score itself.

The eval side of the sealed split is refused unless `--milestone` is given: it is answered only at a milestone, by
the orchestrator. The file is recognised by its bytes (the `eval.jsonl` entry of the split's `manifest.json`), so a
copy under another name is refused too. A part of that file, or the dataset's whole `questions.jsonl`, is not
recognised.

## Adding a real extractor, second counter or question parser

1. Write the adapter in `app/adapters/`. It implements the port's Protocol from `app/core/pipeline/ports.py` or
   `app/core/answering/ports.py`; `app/adapters/hello.py` shows the smallest possible one.
2. Add its name to the port's `Literal` in `app/settings.py` and to `.env.example`.
3. Add a `case` for it in `app/composition.py`.
4. Select it in `backend/.env` (for example `EXTRACTOR_VECTOR=<name>`), rerun the golden set and score it.

`EXTRACTOR_VECTOR=pdf` (`app/adapters/vector_pdf/`, the default) reads a drawn PDF sheet, and the PNG of the same
sheet, from the PDF alone: scale, plans, rooms with areas, apartments and elements for swiss_dwellings plans and for
sheets rendered from an IFC model. Its rules and known misses are in the module docstrings. `EXTRACTOR_VECTOR=hello`
puts the do-nothing extractor back. Every drawing says what was looked for in `read`: a class that is not listed
there was not read, so it has no count.

`SECOND_COUNTER=pdf` (same package) is ingest stage 8 for those sheets. It compares the scale text with
the scale bar, and on swiss plans each printed room area with the room's outline at the sheet's scale. Every
comparison becomes an entry in the drawing's `conflicts`, `agree` or `conflict`, with both values. A conflict is
resolved as `docs/PIPELINE.md` section 2 says, and the drawing carries the resolved value: the bar's scale (and the
areas computed with it), or the printed room area. `SECOND_COUNTER=hello` measures nothing twice.

`EXTRACTOR_BIM=ifc` (`app/adapters/ifc_model/`, the default since 2026-11-14) reads a plan sheet through the IFC
model it was rendered from. It needs three files in the same folder: `<model>.ifc`, the sheet
`<model>_plan-<n>-<storey>.pdf` and the sheet's SVG twin of the same name, whose shapes carry the model's GlobalIds.
The setting also turns on the pairing of a sheet with its model (`DatasetSheetModels`). A sheet without a model or
without the twin stays on the vector route and is read from the PDF alone.

- The elements are the model's objects that the sheet draws, each with its class, storey and GlobalId, so columns,
  stairs, railings, slabs and beams are told apart. The rooms are the drawn IfcSpaces, with number, names and storey.
- `model_objects` lists every object of the model, of every storey, drawn or not: walls with length, side area and
  volume and slabs with volume (the file's own quantities), spaces with their floor area (the footprint of the
  space's solid). `element` names the element or room the sheet draws it as. Sums over a storey and counts "in the
  model" are taken from this list.
- A question on the `.ifc` file itself gets a drawing with no page: `pages: []`, no plans, elements or rooms, and
  the same `model_objects`. A model with none of the classes we list is set aside.

`SECOND_COUNTER=ifc` (the default since 2026-11-14) adds the model's side to stage 8 on such a sheet: what the model
lists on the sheet's storey per element class, against what the sheet draws of that storey, and the storey's spaces
against the rooms drawn. It wraps the `pdf` counter: a sheet without a model gets exactly that counter's readings
(scale text against scale bar, printed room areas against outlines), and a sheet with one gets them too.

Reading a model costs memory: ifcopenshell 0.9.0.post1 does not give a parsed file's memory back, so the models of
one run add up (`app/adapters/ifc_model/objects.py` says what was measured). The largest model in the dataset is
343 MB and takes about 1.1 GB to read.

## What works today

| Part | State |
| --- | --- |
| Inventory with sha256, format from content, grouping by name, routing to the richest format | real, simple rules. With `EXTRACTOR_BIM=ifc` (the default) a plan sheet is also grouped with its IFC model |
| Page sizes of PDF, PNG and JPEG | real |
| Extraction, vector route | `EXTRACTOR_VECTOR=pdf`: swiss plans and IFC-rendered sheets from the PDF alone; other PDFs get their scale only. The default; `hello` stays selectable |
| Extraction, bim route | `EXTRACTOR_BIM=ifc`: a plan sheet read through its IFC model and SVG twin, and a model file on its own (`model_objects`). The default; `hello` stays selectable. Sanitary and light fixtures in a model are not listed: the format has no class for them |
| Extraction, cad and raster routes | hello world: nothing is read, scale `no_scale` |
| Second count | `SECOND_COUNTER=pdf`: scale text against scale bar, printed room areas against outlines (swiss); counts are not measured twice by it. `SECOND_COUNTER=ifc` (the default): those, and on a sheet with a model the element counts per class and the room count of the sheet's storey. `pdf` and `hello` stay selectable |
| Counting rules | rules as data (`pipeline/rules.py`): each item once; saunas are sauna rooms, else stoves; showers plus bathtubs; wall length, side area and volume and slab volume from the elements' IFC quantities; room, indoor and apartment area totals |
| Takeoff | counts, areas, lengths and volumes for the sheet and per storey, by room label, room name or number, and apartment. A quantity the drawing can't give, or of a class not in `read`, has no key, so the question is refused; an empty `read` gives no keys at all, plans included. Areas and lengths on an estimated scale, or summed from estimated room areas, are labelled `estimate`. A quantity with a stage-8 `conflict` entry gives the resolved value and shows both values |
| Question parsing | `QUESTION_PARSER=templates` (default): question words to a takeoff query in 11 languages, no model call. Also the largest room of a type or label, a rectangular room's longer side, and "the apartment" as the sheet's one dwelling. Refuses other superlatives, breakdowns and unquoted places. `hello` stays selectable |
| Schedules | questions that name a schedule, or ask for what only a schedule prints, are answered from `Drawing.tables` (count rows, sum an area column, read cells). The vector extractor reads no tables yet, so this works on gold drawings only |
| Answer prior | `ANSWER_PRIOR=dev` (default `none`): when the drawing gives no value, the answer is the dev answers' mode or median for the question's family, with `abstain: true` and the dev hit rate as `confidence`. The table is built locally from dev questions only (`uv run python -m app.adapters.answer_prior ../data/stoa/split/dev.jsonl`) and never committed |
| Golden v2 (2026-11-14, extras included) | gold drawings: 2876/2948 (97.6%); extras: conflict 12/12 with both values shown, estimate 10/13. Pipeline drawings (`EXTRACTOR_VECTOR=pdf`, `ANSWER_PRIOR=dev`): 2109/2948 (71.5%); 99.0% of the answers that don't abstain are right. With `EXTRACTOR_BIM=ifc SECOND_COUNTER=ifc` as well, the defaults since 2026-11-14 (scratch run, not recorded): 2201/2948 (74.7%), ifc_models 466/466 |
| extraction_v1 and answer_v1 writers, extraction_v1 reader | real, validated against `eval/schemas/` in the tests |
| API | `/health` only |
