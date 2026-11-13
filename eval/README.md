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
uv run python -m stoa_eval select-plans         # golden/v2: part1 files and gold, part2 questions
uv run python -m stoa_eval score-extraction <pred_dir> --name <method>   # Part 1, recorded
uv run python -m stoa_eval validate-extraction ../data/stoa/extraction_gold   # check gold files
uv run python -m stoa_eval validate-extraction --strict-v2 <folder>   # + a scale and room areas
uv run python -m stoa_eval baseline oracle      # golden/runs/oracle.jsonl, must score 100%
uv run python -m stoa_eval baseline constant    # golden/runs/constant.jsonl, the floor to beat
uv run python -m stoa_eval baseline-extraction oracle|empty   # Part 1 baselines (gold, nothing)
uv run python -m stoa_eval score answers.jsonl --name "swiss counts v2" --reads gold-extraction
uv run python -m stoa_eval score answers.jsonl --against dev --name "swiss counts v2"
uv run python -m stoa_eval score answers.jsonl --no-record   # a scratch check, nothing kept
uv run python -m stoa_eval history              # both parts, oldest first, per source
uv run python -m stoa_eval history --progress   # per method: first vs latest vs best
uv run python -m stoa_eval history --csv ../data/stoa/charts   # answering.csv, extraction.csv
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

answer_v1.1 (2026-11-13, amendment to decision 0002) adds optional fields. A v1 line stays valid,
and none of them changes the headline score:

- `confidence`: 0 to 1.
- `abstain`: `true` when the system is too unsure to answer. `answer` still holds the best
  estimate, because Stoa scores `null` as wrong.
- `conflicts`: two or more `{value, unit, method, file, page, box}` for values that disagree
  (`page` and `box` may be null for a value read from an IFC model), with `resolution`, a short
  text saying which value was kept and why.
- `explanation`: how the answer was reached. `excluded`: `{file, page, box, reason}` for regions
  deliberately not counted. `inputs`: the files read.
- An evidence item may also carry `polygon` (page fractions) and `global_id` (an IFC GlobalId).

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

## Golden set v2: two parts

Bogdan, 2026-11-13: "MAke sure the golden is split into 2 parts then. THe extraction, with the
json." `select-plans` picks drawing files and writes both parts to `data/stoa/golden/v2/`:

```
manifest.json                     selection params, split manifest sha256, sha256 of every file
part1_extraction/files.jsonl      one line per file: file, source, split, truth, stratum, scale_case
part1_extraction/gold/<source>/   the extraction_v1 gold of exactly those files
part2_answering/questions.jsonl   every question on those files, all languages, fields as in v1
```

It picks 40 CubiCasa sheets (30 dev, 10 eval), 30 swiss plans (22/8) as both PDF and PNG, 15
ifc_models sheets (11/4) and up to 10 opening_design sheets (8/2, but only 3 have questions). dev
and eval follow the sealed split. Within a source, files are dealt round-robin over strata in
seeded order: CubiCasa sheets with one plan and with several (from the "How many floors" answer),
and each IFC model or opening_design project once before any twice. IFC model files are not
drawings, so their questions are left out. `select-plans` stops if a picked file has no gold JSON
yet; `--allow-missing-gold` lists those files instead.

Every image in golden v2 has a scale value and every room an area (Bogdan, 2026-11-13 23:33: "We
should have ON ALL IMAGES THE SCALE TO GET THE AREA, BY APROXIMATING IT IN DIFFERENT WAYS IF NOT
GOOD SCALE ETC."). `select-plans` also stops if a picked gold file has no `m_per_unit`, still has
a "scale not reviewed" note, or has a room with a polygon and no `area_m2`; schedule sheets
(`truth: tables`) are exempt. `validate-extraction --strict-v2` lists such files, and
`--allow-unscaled` builds anyway and lists them in the manifest under `unscaled`.

Every file in `data/stoa/extraction_gold/_conflicts/conflicts.jsonl` (the conflict slice, below)
joins v2 after the plan and scale picks, so the slice never changes which other files are picked.
Its conflicts are merged into the copied gold file, and the manifest lists them in
`conflict_files`. A file that joins v2 only for the slice gets stratum `conflict` in files.jsonl
and is scored only in the slice: it is no scale case, it stays out of the Part 1 headline, and its
questions stay out of part2 (orchestrator, 2026-11-13 23:29; such files would have added 2,276
questions, 1,738 of them ifc_models, and broken the comparison with earlier runs). Review-10's
conflict questions in the extras cover the answering side. A file already in v2 for its plan or
scale case that also has conflicts stays in the headline as before.

It also builds a scale case list. Every gold file is a scale case except those whose notes start
"scale not reviewed" or "scale dropped", and the case comes from its scale: `scale_text_or_bar`,
`printed_areas` (no text or bar), `dimension_lines` (only), `nothing` (no usable printed evidence:
`estimated`, or `no_scale` in older gold) or `not_to_scale`. Plan picks count first; then more files
join, round-robin over sources in seeded order, until each case has 10 dev and 3 eval files where
the gold has them. Their questions go into part2 as well.

### Part 1: extraction

`score-extraction <pred_dir>` pairs the pipeline's extraction_v1 files
(`schemas/extraction_v1.schema.json`, decision record 0004) with the part1 gold by `file`, and
scores only what the gold's `truth` covers:

- Elements, per class: one-to-one matching on the same page at IoU >= 0.5, greedy from the highest
  IoU. The IoU is of the polygons when both sides have one, else of the boxes. The report gives
  precision, recall and F1, plus two centre-hit rates: predictions whose box centre falls inside a
  gold polygon (or box), and gold items that contain such a centre.
- Rooms are matched the same way, then scored on type and on area. An exact gold area
  (`area_status: exact`, a printed area, or unset as in the swiss and IFC gold) must be within 2%;
  this is the headline room area number. An estimated gold area (CubiCasa: the polygon times an
  approximate scale) is scored like a scale estimate: the relative error of the predicted area, as
  the median and the share within 10% and 20%, per source, with matched rooms that have no
  predicted area counted apart. Plans: exact count.
- Counts per class per file, derived from the lists (or the `counts` object of a `truth: counts`
  file): the exact-match rate, which is what the count questions need. `--multiplicity` counts an
  element `attrs.multiplicity` times.
- Scale, on every scale case (Bogdan, 2026-11-13: "print rooms with areas, calculate it from
  dimension lines, from the scale, and those with nothing say no scale and those who say no scale
  the rsult should be not to scale"). The report has a confusion table of gold status (`scaled`,
  `estimated`, `no_scale`, `not_to_scale`) against predicted status (or a missing file). It also
  gives, per case, whether the status is as expected, and for `scaled` gold the share predicted
  `scaled` with `m_per_unit` within 2%, also per evidence kind. Gold `estimated` expects
  `estimated`: a `scaled` prediction claims a measured scale the sheet doesn't support and is wrong.
  Older gold `no_scale` expects `estimated` or `no_scale`. A predicted value with status
  `estimated` (or a valued `not_to_scale`) on gold that is not `scaled` is an estimate. It is
  compared with the gold's own value (`estimated`, or `not_to_scale` with a value) or else its
  `reference_m_per_unit`, and reported as the median error and the share within 10% and 20%, not
  as pass/fail. Scales compare as metres across the first page, so a prediction rendered at
  another resolution still compares.
- A missing prediction file misses everything on it. A class that no gold file of a source lists
  (no walls in the CubiCasa gold, no stairs in the swiss gold) is not scored for that source, and
  predictions of it are reported as not scored.

Two more sections follow the headline, which they don't change, both in the printed table and in
the run record:

- Tables (schedules on opening_design sheets). A schedule sheet's gold has `truth: "tables"`, and
  only its `tables` are scored (it is not a scale case either). A sheet with a plan and a schedule
  has `truth: "elements"` plus `tables` and is scored on both. A gold table is found by a
  predicted table on the same page with the same title or a box IoU of at least 0.3. Rows pair by
  the cell in the gold table's `key_column` (default 0). Columns pair by position, because the
  gold headers carry group prefixes such as "Door Width", so a differing header is only counted
  as a sanity check. Cells compare after collapsing whitespace and case. The report gives tables
  found, extra predicted tables, row recall (over every gold row), row precision (over the rows of
  found tables) and cell accuracy (the non-key cells of matched rows).
- Conflicts (ingestion stage 8: a second method measures the same quantity). The slice is the
  gold files that list `conflicts`. Gold `conflict` entries are real disagreements somebody looked
  at on the drawing, and `agree` entries are the negatives. A predicted entry pairs with a gold
  entry of the same quantity and subject: the same class, the same sheet, the same apartment (by
  id or label), or the same room under the room matching above, so the pipeline can use its own
  room ids. Per quantity the report gives recall (gold conflicts the prediction calls a conflict),
  false alarms (gold `agree` entries it calls a conflict) and unlisted conflicts (predicted on a
  slice file where gold has no entry; reported, not judged). Predicted conflicts on files outside
  the slice are counted as not scored.

`--against dev` or `eval` scores against every gold file of that split in
`data/stoa/extraction_gold/` instead of v2.

### Part 2: answering

The answerer reads the part1 gold files instead of the drawings and answers
`part2_answering/questions.jsonl`. `score <answers> --against golden` reads part2 by default and
scores with the rules below (`--golden ../data/stoa/golden/golden_v1.jsonl` scores v1). Reading
errors are taken out, so a Part 2 miss is an answering error. Recording a v2 run needs `--reads
gold-extraction`, or `--reads pipeline-extraction` for the same answerer run on the pipeline's own
extraction.

When `part2_answering/extras.jsonl` exists, `score` also scores its lines: questions Stoa didn't
write, all on dev files (schema `schemas/extras_v1.schema.json`, ids from 1000001 up). Each kind is
its own slice, never part of the headline:

- `paraphrase`: the same question in other words, with the same answer. The report gives
  paraphrase accuracy, the accuracy on their origin questions in the same answers file, and the
  gap between the two. A negative gap means the answering depends on the template's wording.
- `unanswerable`: the drawing can't tell (no scale for an area, a fact no plan shows). It passes
  only with `abstain: true`.
- `conflict`: a question about a quantity in the conflict slice. It passes when both
  `expect.conflict_values` appear in the answer's `conflicts` (matched by the answer rules, in the
  line's unit) and the answer is right.

When answers to the golden questions carry `confidence` or `abstain`, the report also gives the
abstain rate, the accuracy of abstained and of other answers (the best estimate is judged), and a
calibration table: confidence buckets 0.2 wide against accuracy. `baseline oracle` answers the
extras too, so it must score 100% on every slice.

Review-7 writes its lines (ids up to 1000999) straight into `part2_answering/extras.jsonl`.
Review-10 writes its conflict lines (1001001-1001999) to
`data/stoa/extraction_gold/_conflicts/extras.jsonl`, and `select-plans` merges them by id. Lines
in review-10's range are replaced on every run, and review-7's lines are kept byte for byte. Every
line is checked first (its file is a dev file of v2, a paraphrase's origin is a v2 question), and
a bad line stops the run before anything is written.

### Where a wrong answer comes from

Run the answerer on the same questions twice, once on the gold
extraction and once on the pipeline's. Wrong both times: the answering is wrong. Right on gold but
wrong on the pipeline's: the extraction is wrong, and the file's `per_file` entry in the Part 1
score JSON shows which counts were off and what happened to the scale. Right on the pipeline's but
wrong on gold: check the gold file and the dataset answer.

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

Every scored run is kept, so that at the end we can show how the methods improved (owner,
2026-11-13: "also make sure all the runs of the golden dataset, will be saved somewhere so at the end
we will be able to show the improvement"). `score` and `score-extraction` record each run against
`golden` or `dev` and need `--name <method>` for it (`--note "..."` is optional). `--no-record`
keeps nothing, for scratch checks and tests. The eval split, and `--against all` which contains it,
is scored only as a recorded `--milestone` run or with `--no-record`.

Each run is one file in `results/runs/`, named `<YYYYMMDD-HHMMSS>-<part>-<name>.json` (`-2`, `-3`
when two runs share a second), so PRs from different people never touch the same file. Commit the
files your runs wrote with your PR. The full score (per question or per file) goes to the gitignored
`data/stoa/golden/runs/` under the same name, and the history file keeps its sha256.

A history file holds the time (Europe/Helsinki), the git commit with a dirty flag, the method name
and note, the part and what was scored (golden version, dev, eval or all; for v2 Part 2 also what
the answerer read), and aggregates only. Part 2 files (`schemas/run_record_v1.schema.json`) hold
overall, numeric and per source/type counts and accuracy (plus coverage for dev, eval and all),
evidence coverage, cost and latency. Part 1 files (`schemas/extraction_record_v1.schema.json`) hold
element and room F1, plan and count exact rates, scale status and `m_per_unit` pass rates and the
median estimate error, overall and per source, and the estimated room areas per source. A Part 1
file also holds the tables and conflict
sections when the gold has them, and a Part 2 file the extras and answer_v1.1 sections (aggregates
and the extras file's sha256). Records written before these sections still load. No file holds
question text, answers, templates or file names, because the repo is public; the schemas refuse
any other key.

`history` prints Part 1 and Part 2 as separate tables, oldest first, with per-source columns (Part 1:
element F1, counts exact, scale status ok; Part 2: accuracy). `--part` shows one part, `--against`
one target, and `--csv <folder>` writes `answering.csv` and `extraction.csv` for a chart.
`history --progress` gives, per method name and target, the first, latest and best value of each
headline number and the change from first to latest.

Compare methods on holdout or eval. Near-duplicate questions inside dev (one building shipped as two
models, identical typical floors) lift the constant baseline's dev score.
