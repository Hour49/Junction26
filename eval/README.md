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
uv run python -m stoa_eval select-plans --keep ../data/stoa/golden/v2/manifest.json   # rebuild v2
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
uv run python -m stoa_eval series               # the `pipeline` series as a markdown table
./pipeline-run.sh <commit> [NAME=VALUE ...]     # record one point of the series (below)
uv run python -m stoa_eval schema               # rewrite schemas/ after changing a model
uv run python -m stoa_eval exp-split            # data/stoa/exp/split.json: CubiCasa train/val/test
uv run python -m stoa_eval ab --a <arm> --b <arm>   # A/B two arms on val (Experiments, below)
uv run python -m stoa_eval gate --arm <arm>        # E5 confidence gate on val (--second <arm>)
uv run python -m stoa_eval gate-policy --gate <val gate JSON> [--certificate <test gate JSON>]  # gate.json
uv run python -m stoa_eval gate-refit [--detector <val output>]  # gate.json refit on a runtime config
uv run python -m stoa_eval leaderboard          # every arm under data/stoa/exp against prior on val
uv run python -m stoa_eval annotated-region     # the region each train/val image's gold annotates
./check.sh                                      # lint, format, types, tests, audit, as in CI
```

`split` and `select` need the full dataset (`python3 tools/fetch_stoa_data.py full` from the repo
root). Run `split` before `select`.

## Experiments (CubiCasa raster, 2026-11-14)

`exp-split` cuts the CubiCasa images with questions in `split/dev.jsonl`, minus every golden v2 file, into
train / val / test (80/10/10 of drawing groups, seeded by `split.rank`, so a rerun writes the same bytes) and
writes `data/stoa/exp/split.json` (files and gold class totals per part) and `<part>_questions.jsonl` (the dev
lines, ids kept). It stops on an image in an eval group, a golden v2 image, or gold not marked dev.

`ab` compares two arms on val (or test, once, for the shipped arm). An arm is a folder of extraction_v1 files
(one per image, matched by `file`), or `gold`, `prior` (answer's prior refit on `train_questions.jsonl`, written
to `data/stoa/priors/exp-train.json`) or `none` (every image read, nothing found). `ab_backend.py` answers the
questions in backend/'s own environment with `build_pipeline(...).answer_questions` over the arm's folder, the
templates parser and no prior, so the takeoff is the pipeline's. Stoa's rule judges each answer, and an image
without a file is refused and wrong. The report gives the exact rate overall, per family and per style; B - A
with a 95% bootstrap interval over images (10,000 resamples, seed 20261114), which alone gives the verdict,
overall and per family (a family's interval holds for a family named in advance; across 12 families about 1 in
20 excludes 0 by chance), and an exact McNemar p (over questions: EN/FI pairs on one image are not independent, so it is overconfident); the
count
per key against the dev gold (exact share, MAE); and each arm's 10 images with the most wrong answers. JSON
goes to `data/stoa/exp/ab/<a>-vs-<b>-<part>.json`. `--orientation <json>` (file -> label) splits by
orientation; the gold has none.

`gate` (E5) scores each answer (a family on an image) with four built-in signals: `top3` (mean of the 3 highest
`attrs.score` of the family's detections), `pb_mode` (probability of the modal Poisson-binomial count, scores
calibrated by isotonic regression against IoU >= 0.5 matches with the gold, on a seeded half of val) and `agree`
(a second arm gives the same answer) and `agree_pb` (agree + pb_mode: agreeing answers first, ordered by
pb_mode). An answer where the arm found nothing gets, as pb_mode, the calibration half's exact rate of such
answers in its family, (exact + 1) / (n + 2), not 1. `--signal-file f.json` (repeatable) adds any other
producer's signal: `{"schema": "gate_signal_v1", "name": "decide", "arm": "detector/C-yolo26s-v8" or null,
"values": [{"file": "data/cubicasa5k/x.png", "family": "door", "value": 0.93}, ...]}`, one value per family
and image, higher is surer; family names as the gate prints them (door, window, toilet, sink,
shower+bathtub, sauna, plan, room:<type>). A file for another arm, an unknown family, a built-in name or two
values for one answer are refused; an answer without a value is never sure; `--part test` needs the same
`--signal-file` (with test values) when the val gate chose it. A refused answer gets no signal. On the other half of val it reports
failure AUROC and risk-coverage per signal, and per family the loosest threshold Learn-then-Test certifies
(fixed sequence strict to loose, exact binomial p of error >= 5%, delta 0.05 divided by the number of families).
`--pool` gives each family group (elements, plans, rooms) one threshold instead, with the plan as the unit (a plan
with a sure answer of the group is wrong when any of them is): the loosest threshold whose one-sided 95%
Clopper-Pearson bound on the val plans meets the target, every threshold tested, delta not split, because a val
pick is a choice and not a guarantee (the output says "chosen on val, not a guarantee" wherever it prints val
numbers). The certificate counts a plan wrong when any of its sure answers is, over all groups at once, so if
the groups' own picks miss the target together, groups are tightened one threshold at a time (the move that
removes the most wrong plans per sure plan lost) until they meet it; the output shows each group's own pick
beside the final one (`alone_*`, `union_steps` in the JSON). Families too small to open alone can open
together; `--part test` reuses the val file's groups and thresholds unchanged. Val only picks thresholds. `--part test --certify` applies the val calibration and thresholds and prints "of
the plans marked sure, at least X% have every sure answer exact (N plans, 95% bound); the gate opens on Y% of
plans" (one-sided Clopper-Pearson, the plan as the unit). JSON goes to `data/stoa/exp/ab/gate-<arm>-<part>.json`.

The gate of what the product runs: `--family-arm 'room:*=<folder>'` (repeatable; a family or a pattern) answers
those families from another arm, as a runtime combination does (the arm's name becomes `<arm>+<other>`, the
JSON records `family_arms`, and `--part test` needs the same routing). Built-in signals have no value on a routed
family (they read `--arm`'s extraction), and a signal file about one arm is refused. `--g1main <folder>` adds the
signal `g1main`, the backend's DECISIONS_CONFIDENCE on the gate's own answers: decide's cached G1main replies
(`data/stoa/exp/decide/G1main-high/raw`, checked against the backend's question set) read by the backend's parser
(`ab_backend.py g1main`), Gemini's probability for each answered count, the lowest over a family's questions on an
image, none for an answer that is not a whole count. `--swap S1536` (needs `--g1main`) applies the runtime's
Decisions count swap to `--arm`'s answers with the backend's own rule and frozen thresholds (`ab_backend.py
swap`: `app.adapters.decisions.uses.swapped`, `SWAP_ARMS`), so the gate judges the counts the product gives; the
built-in signals then have no value (they read the unswapped extraction).

`gate-refit` is all of that in one command for a runtime config: the pooled g1main gate on val with the swap and
the rooms arm the runtime has, then `data/stoa/exp/gate.json` from it, printing the file before and after.
Defaults are the demo config (`tools/qa-env.sh config`, 2026-11-14): `--detector data/stoa/exp/region/L1536-R1`
(region:C-yolo26s-1536's val output), `--swap S1536` (decisions-s1536), `--rooms data/stoa/exp/ocr/G4-regpred`
(regionrooms), `--g1main data/stoa/exp/decide/G1main-high/raw`. A new detector: give its val output folder
(`--detector`), and `--swap none` or another `SWAP_ARMS` arm if the runtime changes the swap. When the folder is
the backend's own run of the whole config (swap and rooms already in it), give `--swap none --rooms none`.
Config C (2026-11-14, golden-19) was refit that way:
`gate-refit --detector ../data/stoa/exp/ab/runtime-C-L-swap --swap none --rooms none --g1main
../data/stoa/exp/integ/decisions-cache-val`.

`--g1main` takes decide's cache (`{file, request, response}` per image) or the backend's own
`DECISIONS_CACHE_DIR` (names `<image sha256>-<question set>-<model>-<resolution>.json`): the backend's
G1MainReader reads the latter for each drawing of the part from its bytes, as at runtime, and never calls the
API (a drawing not cached gets no score: never sure). On val the two give identical distributions (376 of 376).

`gate-policy` turns a val gate JSON into `data/stoa/exp/gate.json` (gate_policy_v1, schema in
docs/GOLDEN.md): per family whose gate opens on val answers, the signal, threshold, group and val numbers
("chosen on val, not a guarantee"), the split sha256 (required) and `certified: false` until the test run.
`--certificate <data/stoa/exp/ab/gate-<arm>-test.json>` adds that test run as `test` and sets `certified` when
its bound meets the target; a test file of another gate (arm, split, signal or a threshold differs) is refused.

`annotated-region` writes `data/stoa/exp/labels/annotated_region.json` for every train and val image (never
test, eval or golden v2; it stops on one): the region the dev gold annotates, as outer rings in pixels (gold
rooms, elements and empty plans, each grown 0.5 m, merged), usable as a training ignore mask, and `extends`
when the drawing visibly goes on beyond it. `ink_outside` is measured on the image alone: dark ink more than
0.25 m beyond the region over dark ink inside, leaving out a 1% border band, solid fills at least 0.5 m thick
and rows or columns dark across 90% of the sheet. `extends` is `ink_outside >= 0.2`; on 40 unseen images
labelled by eye, 17 of 20 flagged ones extend, and 1 of 20 unflagged hq_arch ones clearly does (7 more show
slivers). Pick another cut on `ink_outside` if you need more recall. About 3.5 minutes on one core.

`leaderboard` scores every arm under `data/stoa/exp` (an arm = a folder of extraction_v1 files with val
images) against the train prior and writes `.agents/exp/leaderboard.md`, `data/stoa/exp/ab/leaderboard.json`
and `data/stoa/exp/policy.json`: per family, the best arm on val whose paired interval against the prior lies
above 0, else the prior. Oracle arms (gold at answer time) are scored but never picked: an `ORACLE` text file in
the arm folder or a parent (saying what gold it reads), a glob in `data/stoa/exp/oracles.json`
(`{"schema": "oracle_arms_v1", "arms": {"ocr/*-reg": "why"}}`), or "oracle" / "gold" in the path; policy.json
lists them under `oracles_never_picked`. `families` applies the rule only to arms with golden v2 output (a
sibling folder `<arm>-golden`, so the pipeline can run them end to end) and names that folder per family: the
backend's ANSWER_POLICY reads it and integ runs it on golden v2. `families_any_arm` is the same rule over every
arm, for information only.

Test is used once per arm: `ab --part test` and `gate --part test` need `--certify`, append the run (arm,
time, result, result file sha256) to `data/stoa/exp/test-certified.json`, and refuse an arm already run on
test by the same command unless `--recertify-reason "<why>"` is given.

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
- `estimate`: `true` when the value rests on an estimated scale or reading (say from what in
  `explanation`); 2026-11-13 23:48.

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

The v2 file set is frozen (orchestrator, 2026-11-13 23:48): rebuild it with `--keep
../data/stoa/golden/v2/manifest.json`. That keeps every file of the earlier build (its
part1_extraction/files.jsonl, checked against the manifest's sha256) with its split and stratum,
skips the plan and scale picks, and recomputes the conflict slice and every file's scale case from
the current gold. The manifest's `kept` is the sha256 of the kept list.

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
- `read` (optional, 2026-11-13, golden-7f): the element classes, and `room`, that the extraction
  looked for; left out (as in all gold) it means everything the file's `truth` covers. A class not
  listed was not read, so its count is unknown rather than 0. Scoring is the same either way: not
  reading a class counts its misses. The element table marks `not read` on a class that every
  prediction file of the source leaves out.

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
- `unanswerable`: the drawing can't tell (a fact no plan shows). It passes only with `abstain:
  true`.
- `estimate`: an area or length on a sheet whose only scale is estimated. It passes when the
  value is within `expect.tolerance` (relative, 0.2) of `expect.answer`, in the line's unit or
  one converted as for answers, and the answer says `estimate: true`. The report also gives how
  many values were right and how many were labelled.
- `conflict`: a question about a quantity in the conflict slice. It passes when both
  `expect.conflict_values` appear in the answer's `conflicts` (matched by the answer rules, in the
  line's unit) and the answer is right.

When answers to the golden questions carry `confidence` or `abstain`, the report also gives the
abstain rate, the accuracy of abstained and of other answers (the best estimate is judged), and a
calibration table: confidence buckets 0.2 wide against accuracy. `baseline oracle` answers the
extras too, so it must score 100% on every slice.

Two more sections follow the headline without changing it:

- Evidence hit rate (`stoa_eval/evidence_scoring.py`). For a numeric question on a file whose
  part1 gold has truth `elements`, the wording gives the subject (an element class, a room type,
  the rooms with a label, number or name, an apartment's indoor rooms, the numbered indoor rooms,
  all rooms, the plans; saunas mean the sauna stoves) and the subject picks gold items. A box hits
  an item when it is on the question's file and the item's page and its centre lies in the item's
  gold box. Precision: hit boxes / boxes. Recall: items some box hits / items. Both are pooled,
  per source and per source/subject. A question without an answer line or without boxes adds its
  items to recall. Text questions, files with truth `counts` or `tables`, apartment counts and
  whole-model IFC questions are not scored, and the report counts them by reason. The module
  docstring says why the centre and not IoU. `baseline oracle` cites one box per item, so it must
  score 100%/100%.
- Text by claims (`stoa_eval/text_scoring.py`, D52). When `part2_answering/text_claims.jsonl`
  exists (schema `schemas/text_claims_v1.schema.json`, one line per golden text question id with
  `numbers` and `names`), a text answer passes when every number claim is met one to one (counts
  exactly, measures within 2% after converting length, area and time units) and every name, or one
  of its aliases, appears as whole words. The report gives the pass rate for dev and holdout, the
  share of number and name claims met, and the text questions without claims. The headline's text
  line stays exact match. Claims for an id that is not a golden text question, or a repeated id,
  stop the run.

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
keeps nothing, for scratch checks and tests: the full score is written only to `--out <file>`, and
without it nowhere. The eval split, and `--against all` which contains it,
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
sections when the gold has them, and a Part 2 file the extras, answer_v1.1, evidence hit rate
(`evidence_hits`: overall, per source, per source/subject) and text claims (`text_claims`)
sections (aggregates and the extras and claims files' sha256). Records written before these sections still load. No file holds
question text, answers, templates or file names, because the repo is public; the schemas refuse
any other key.

Since 2026-11-14 a record also says which code made the predictions and how it was set up.
`commit` and `dirty` describe that code, and `committed_at` is its commit time. By default that is
this tree's HEAD. With `--commit <sha>` the predictions came from a clean export (`git archive`) of
that commit: the record says `dirty: false`, and `eval_commit` / `eval_dirty` name the scorer that
scored them. `--setting NAME=VALUE` (repeatable) keeps the settings the run used, names lowercased,
values plain words (no paths). Part 2 records also keep accuracy per split (`by_split`: dev and
holdout for the golden set).

`history` prints Part 1 and Part 2 as separate tables, oldest first, with per-source columns (Part 1:
element F1, counts exact, scale status ok; Part 2: accuracy). `--part` shows one part, `--against`
one target, and `--csv <folder>` writes `answering.csv` and `extraction.csv` for a chart.
`history --progress` gives, per method name and target, the first, latest and best value of each
headline number and the change from first to latest. Runs go in code order: a clean run counts at
its commit time and a run with uncommitted changes at the time it was recorded, so a run backfilled
from an old commit counts as early. The CSVs carry that `code_time`, the settings, and for Part 2
the accuracy per split and the abstain rate.

### The `pipeline` series

`pipeline` is the method name for the product end to end on golden v2: Part 1 read from the
drawings (`--drawings pipeline`), Part 2 answered from that extraction (`--reads
pipeline-extraction`), with every real adapter of the commit turned on. Each commit gives one
point, run from a clean export rather than the shared tree:

```bash
systemd-run --user --scope -p MemoryMax=6G nice -n 15 \
  ./pipeline-run.sh 85d3470 EXTRACTOR_VECTOR=pdf QUESTION_PARSER=templates
```

The script exports `backend/` of that commit into `data/stoa/runs/pipeline-<sha>-<time>/export/`
(delete it when done), builds the dev prior there when `ANSWER_PRIOR=dev`, reads back the
settings the export runs with, runs `app.cli golden`, and records both parts with `--commit` and
every setting. `series` prints the points as a markdown table: commit, commit time, the settings
that change, Part 1 element F1 per source, Part 2 accuracy overall, dev and holdout, and the share
of answers marked `abstain`. A dev cell marked † is in-sample: with `answer_prior=dev` an abstained
answer carries the dev prior's value, and the prior is fit on `dev.jsonl`, which holds the golden
dev questions. The holdout column is the honest number for the prior. docs/GOLDEN.md has the
current table.

Compare methods on holdout or eval. Near-duplicate questions inside dev (one building shipped as two
models, identical typical floors) lift the constant baseline's dev score.
