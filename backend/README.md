# backend

The product pipeline: it reads drawing files into one drawing model per file, then answers quantity questions from
that model. Python 3.13, ports and adapters. The design is in
[docs/decisions/0005-pipeline-core.md](../docs/decisions/0005-pipeline-core.md), the stages in
[docs/PIPELINE.md](../docs/PIPELINE.md).

Today every stage is a do-nothing "hello world": the pipeline runs end to end on the golden set and scores near
zero. Each real feature replaces one adapter or one stage, and the next scored run shows what it gained.

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

## Adding a real extractor, second counter or question parser

1. Write the adapter in `app/adapters/`. It implements the port's Protocol from `app/core/pipeline/ports.py` or
   `app/core/answering/ports.py`; `app/adapters/hello.py` shows the smallest possible one.
2. Add its name to the port's `Literal` in `app/settings.py` and to `.env.example`.
3. Add a `case` for it in `app/composition.py`.
4. Select it in `backend/.env` (for example `EXTRACTOR_VECTOR=<name>`), rerun the golden set and score it.

`EXTRACTOR_VECTOR=pdf` (`app/adapters/vector_pdf/`) reads a drawn PDF sheet, and the PNG of the same sheet, from the
PDF alone: scale, plans, rooms with areas, apartments and elements for swiss_dwellings plans and for sheets rendered
from an IFC model. Its rules and known misses are in the module docstrings.

## What works today

| Part | State |
| --- | --- |
| Inventory with sha256, format from content, grouping by name, routing to the richest format | real, simple rules |
| Page sizes of PDF, PNG and JPEG | real |
| Extraction, vector route | `EXTRACTOR_VECTOR=pdf`: swiss plans and IFC-rendered sheets from the PDF alone; other PDFs get their scale only. Default is still `hello` |
| Extraction, bim, cad and raster routes | hello world: nothing is read, scale `no_scale` |
| Second count | hello world: nothing is measured twice, so no conflicts |
| Counting rules | one rule: every listed item counts once |
| Takeoff | counts per element class, room type and plan; no areas, lengths or volumes |
| Question parsing | hello world: every question is refused |
| extraction_v1 and answer_v1 writers, extraction_v1 reader | real, validated against `eval/schemas/` in the tests |
| API | `/health` only |
