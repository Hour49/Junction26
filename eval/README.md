# eval: sealed split, golden set and scorer

This seals 20% of the Stoa questions as an eval split, picks the golden set, runs two baselines
that need no API, and scores an answers file against the golden set or against every question.
Everything it writes goes to `data/stoa/split/` and `data/stoa/golden/`, which are gitignored
because they are derived from partner data.

## Commands (in `eval/`)

```bash
uv sync --locked
uv run python -m stoa_eval split                # split/dev.jsonl, split/eval.jsonl, split/manifest.json
uv run python -m stoa_eval select               # golden/golden_v1.jsonl and its manifest
uv run python -m stoa_eval baseline oracle      # golden/runs/oracle.jsonl, must score 100%
uv run python -m stoa_eval baseline constant    # golden/runs/constant.jsonl, the floor to beat
uv run python -m stoa_eval score ../data/stoa/golden/runs/oracle.jsonl   # table and oracle.score.json
uv run python -m stoa_eval score answers.jsonl --against dev   # every dev question
uv run python -m stoa_eval score answers.jsonl --against dev --record --name "swiss counts v2"
uv run python -m stoa_eval history --csv ../data/stoa/history.csv   # all recorded runs, oldest first
uv run python -m stoa_eval schema               # rewrite schemas/ after changing a model
./check.sh                                      # lint, format, types, tests, audit, as in CI
```

`split` and `select` need the full dataset (`python3 tools/fetch_stoa_data.py full` from the repo
root). Run `split` before `select`.

## Answer format (answer_v1)

One JSON line per question. The schema is `schemas/answer_v1.schema.json`; the decision record is
`docs/decisions/0002-answer-format.md`.

```json
{"id": 1234, "answer": 12.5, "unit": "m2", "evidence": [{"file": "data/swiss_dwellings/x.pdf", "page": 1, "box": [0.1, 0.2, 0.3, 0.4]}], "method": "vision", "cost_usd": 0.002, "latency_s": 1.5}
```

- `id` is the question's 1-based line number in `questions.jsonl`, the same id the golden and
  split rows have.
- `unit` is one of `count`, `m`, `m2`, `m3`, `ft`, `ft2`, or `null` for text.
- `box` is `[x0, y0, x1, y1]` in fractions of the page width and height, origin top left.
- `evidence` may be empty. `answer: null` means no answer.

## Sealed split

About 20% of the questions go to `eval.jsonl`, and everything we build or tune uses only
`dev.jsonl` (owner, 2026-11-13). The split keeps whole drawing groups together: a drawing in all its
formats, an IFC building with its plans and discipline models, or an `opening_design` project. Each
source's groups join eval in seeded order while they fit under 20% of that source's questions. The
manifest records the seed, the sha256 of `questions.jsonl` and of both outputs, the counts per
source and per source/type, and the eval groups. Score against eval at milestones only.

## Golden set v1 (provisional)

- A cell is source × type × language. Each cell gets 4 questions: 3 dev and 1 holdout, with holdout
  items taken only from eval groups. When a cell has questions in only one split (common for IFC
  models, where a language often means one building), that split supplies all 4. Picks rotate over
  the cell's question templates and prefer different drawings.
- `--cell-keys`, `--per-cell`, `--holdout-ratio`, `--seed` and `--version` change all of this.

## Scoring

- Counts must be exact. Areas, lengths and volumes must be within 2% of the golden value, in the
  golden unit or converted from m/ft or m2/ft2 (no other conversions).
- Text answers must match after normalising (NFKC, case, whitespace, a trailing full stop). They are
  also listed under `needs_review` in the score file, because the dataset scores text free-form.
- Against the golden set (the default), a missing answer is wrong. The report shows overall,
  numeric, text, dev, holdout and per source/type accuracy, the reasons for misses, evidence coverage
  (share of questions with at least one box), cost and latency.
- `--against all`, `dev` or `eval` scores every question of the split. This is meant for parsers
  that cost nothing per question and answer only some of them. An unanswered question is not wrong
  here: the report gives coverage (answered / questions) and accuracy on the answered questions,
  overall, per split, per source/type and per question template (most answered first, `--top`
  printed). Evidence coverage counts answered questions only.

## Results history

`score --record --name <method> [--note "..."]` appends one row to `results/runs.jsonl`, which is
tracked so that at the end we can show how the methods improved (owner, 2026-11-13). A row holds
the time (Europe/Helsinki), the git commit with a dirty flag, the method name and note, what was
scored (golden set version, dev, eval or all), the sha256 of `questions.jsonl` and of the full score
file, and aggregates: overall, numeric and per source/type counts and accuracy (plus coverage for
dev, eval and all), evidence coverage, cost, and mean and p95 latency. It never holds question
text, answers, templates or file names, because the repo is public; the schema
(`schemas/run_record_v1.schema.json`) refuses any other key. Recording a run against eval needs
`--milestone`. `history [--against ...] [--csv file]` prints the rows oldest first and can write a
CSV for a chart. Rows are only ever appended.

Compare methods on holdout or eval. Near-duplicate questions inside dev (one building shipped as two
models, identical typical floors) lift the constant baseline's dev score.
