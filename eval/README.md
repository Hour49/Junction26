# eval: golden set and scorer

This picks the golden set from the Stoa questions, runs two baselines that need no API, and scores
an answers file against the golden set. The golden set and every run are written to
`data/stoa/golden/`, which is gitignored because they are derived from partner data.

## Commands (in `eval/`)

```bash
uv sync --locked
uv run python -m stoa_eval select               # golden_v0.jsonl and golden_v0.manifest.json
uv run python -m stoa_eval baseline oracle      # runs/oracle.jsonl, must score 100%
uv run python -m stoa_eval baseline constant    # runs/constant.jsonl, the floor to beat
uv run python -m stoa_eval score ../data/stoa/golden/runs/oracle.jsonl   # table and oracle.score.json
uv run python -m stoa_eval schema               # rewrite schemas/ after changing a model
./check.sh                                      # lint, format, types, tests, audit, as in CI
```

`select` needs the full dataset (`python3 tools/fetch_stoa_data.py full` from the repo root).

## Answer format (answer_v1)

One JSON line per question. The schema is `schemas/answer_v1.schema.json`.

```json
{"id": 1234, "answer": 12.5, "unit": "m2", "evidence": [{"file": "data/swiss_dwellings/x.pdf", "page": 1, "box": [0.1, 0.2, 0.3, 0.4]}], "method": "vision", "cost_usd": 0.002, "latency_s": 1.5}
```

- `id` is the question's 1-based line number in `questions.jsonl`, the same id the golden row has.
- `unit` is one of `count`, `m`, `m2`, `m3`, `ft`, `ft2`, or `null` for text.
- `box` is `[x0, y0, x1, y1]` in fractions of the page width and height, origin top left.
- `evidence` may be empty. `answer: null` means no answer and is scored wrong.

## Golden set v0 (provisional)

- `select` splits the dataset by drawing group before it picks any question. A group is a drawing
  in all its formats, an IFC building with its plans and discipline models, or an `opening_design`
  project. Each source's groups go to dev or holdout by seeded hash, so every question in the
  dataset has a split. The manifest lists the holdout groups: don't tune on them.
- A cell is source × type × language. Each cell gets 4 questions, 2 dev and 2 holdout. When a
  cell has questions in only one split (common for IFC models, where a language often means one
  building), that split supplies all 4. Picks rotate over the cell's question templates and prefer
  different drawings.
- `--cell-keys`, `--per-cell`, `--holdout-ratio`, `--seed` and `--version` change all of this.

## Scoring

- Counts must be exact. Areas, lengths and volumes must be within 2% of the golden value, in the
  golden unit or converted from m/ft or m2/ft2 (no other conversions).
- Text answers must match after normalising (NFKC, case, whitespace, a trailing full stop). They are
  also listed under `needs_review` in the score file, because the dataset scores text free-form.
- A missing answer is wrong.
- The report shows overall, numeric, text, dev, holdout and per source/type accuracy, the reasons
  for misses, evidence coverage (share of questions with at least one box), cost and latency.

Compare methods on holdout. Near-duplicate questions inside dev (one building shipped as two
models, identical typical floors) lift the constant baseline's dev score; holdout doesn't have that.
