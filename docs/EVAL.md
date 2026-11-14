# The Stoa challenge, the golden set and the eval in short

Moved here from the README on 2026-11-14, text unchanged apart from the links. The full method and every result
are in [GOLDEN.md](GOLDEN.md); the commands and exact scoring rules are in [eval/README.md](../eval/README.md).

Stoa's challenge is to answer questions about construction drawings and BIM models, and to show where each answer
came from. The judges weigh four things equally: accuracy, how well the reasoning is shown, creativity and low
inference cost. Our golden set is the fixed exam we grade every version of our system against, using Stoa's own
answers and scoring rules.

```text
questions.jsonl (Stoa: 127,044 questions with answers)
   ├── split by drawing/building ──► dev 80%  (build and tune on this)
   │                                 eval 20% (sealed: scored only at milestones)
   └── golden set (small stratified sample: dev items from the 80%, holdout items from the 20%)

our system ──► answers.jsonl (one line per question) ──► stoa_eval score ──► report + results history
```

1. Data. `tools/fetch_stoa_data.py` downloads the dataset into the gitignored `data/` folder (see
   [data/README.md](../data/README.md)). Partner data never enters the repo.
2. The answers we grade against. Each line of `questions.jsonl` has a file, a question, the expected answer, a
   unit and a type (count, area, length, volume, text). We take Stoa's answer as correct. Our review of the dataset
   found it reliable. Ambiguous or likely-wrong items get tagged and are kept out of the headline score.
3. Splits. 20% of all questions form a sealed eval split, chosen by drawing, building or model, so translations
   of a question and the floors of one building stay on one side. Build and tune only on the 80% dev split. Score
   eval at milestones, to catch overfitting. Today: 101,651 dev and 25,393 eval questions (decided 2026-11-13).
4. The golden set. A small fixed sample that covers every source, question type and language, plus the known
   traps (rotated plans, sheets with several plans, 1:200 scale, rooms with cut-outs, ...). It is small because
   vision and LLM answers cost money per question. Free parsers are scored on all questions. v1 has 152 questions
   (107 dev, 45 holdout from the eval split).
5. What our system writes. One answer_v1 line per question ([decision 0002](decisions/0002-answer-format.md)):
   ```json
   {"id": 89501, "answer": 212.41, "unit": "m2",
    "evidence": [{"file": "data/swiss_dwellings/....pdf", "page": 1, "box": [0.31, 0.22, 0.38, 0.29]}],
    "method": "pdf-vector", "cost_usd": 0.0, "latency_s": 0.04}
   ```
   `answer` is graded for accuracy. `evidence` boxes (page fractions) show where on the drawing the answer came from.
   `cost_usd` and `latency_s` cover the cost criterion.
6. Scoring (Stoa's rules). Counts must be exact. Areas, lengths and volumes pass within 2%, and only m↔ft and
   m²↔ft² are converted. On the golden set a missing answer is wrong; against all, dev or eval questions the report
   gives coverage and accuracy on the answered ones. Free text needs an exact match for now. The report breaks
   accuracy down by source, type and template, and adds evidence coverage, cost and latency.
7. Baselines. `oracle` (Stoa's own answers) must score 100%, which proves the plumbing. `constant` (the most
   common answer per question template, learnt from dev) scores 15.8% on golden v1, and any real method has to beat
   it.
8. Results history. Every scored run is recorded by default as one summary file (time, commit, method, split,
   accuracy per source and type, coverage, cost, latency; no questions or answers) in [eval/results/runs/](../eval/results/runs/),
   so we can show how we improved; `--no-record` is for scratch checks. `stoa_eval history` prints the runs,
   `--progress` shows first vs latest vs best per method, `--csv` exports them for a chart.

```bash
cd eval
uv run python -m stoa_eval split                  # sealed 80/20 split into data/stoa/split/ (same hashes everywhere)
uv run python -m stoa_eval select                 # build the golden set into data/stoa/golden/
uv run python -m stoa_eval baseline oracle        # or: constant
uv run python -m stoa_eval score <answers.jsonl> --against dev --name <method>   # grade it; the run is kept
uv run python -m stoa_eval history                # every recorded run, oldest first
```

More in [eval/README.md](../eval/README.md). First real methods: [prototypes/pdf-extract/](../prototypes/pdf-extract/README.md)
answers swiss and ifc_models questions from the PDF alone, with no model call (99.91% on swiss counts, 99.97% on swiss
areas, 96.99% on ifc_models room areas; tuned on all questions, so not a held-out result).
