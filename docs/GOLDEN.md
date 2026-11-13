# The golden set

This is how team Hour49 measures its answers to the Stoa questions: what the golden set contains, how it is
picked, how each part is scored, and how results are kept. It replaces the spec draft in PR #12 (spec decision 5,
accepted by Bogdan on 2026-11-13 at 23:03). The commands and the exact scoring rules are in
[eval/README.md](../eval/README.md); the file formats are decision records
[0002](decisions/0002-answer-format.md) (answers) and [0004](decisions/0004-extraction-format.md) (extractions).

Everything the scripts write from partner data goes to `data/stoa/` and is gitignored. The repo only holds code,
schemas and run records with aggregate numbers.

## What we measure

Stoa judges accuracy (counts exact; areas, lengths and volumes within 2%), whether the answer shows a person where
it came from, creativity, and inference cost. The golden set is a fixed sample of the dataset on which we measure
accuracy, evidence and cost the way Stoa does, so a change to the system shows up as a number. The demo takes its
examples from it, and it is the team's shared definition of a right answer.

## The sealed split

Bogdan, 2026-11-13 20:25: "also keep 20% of the questions not in the dataset so we can use that as an eval".
`split` puts about 20% of all 127,044 questions into `data/stoa/split/eval.jsonl`, by drawing group: a drawing in
all its formats, an IFC building with its plans and discipline models, or an opening_design project stay on one
side. Everything we build or tune uses only `dev.jsonl`. The eval split is scored only at milestones, and every
golden file picked from it is a holdout item. The swiss and IFC extractor rules were tuned before the split
existed, so their eval numbers are not blind.

## Golden v2: two parts, picked by drawing

Bogdan, 2026-11-13 ~22:10: "MAke sure the golden is split into 2 parts then. THe extraction, with the json."
Scoring only answers cannot tell a misread drawing from a wrong answer, so v2 has two parts over the same files:

- Part 1, extraction: for each picked drawing, a gold extraction (extraction_v1 JSON: pages, scale, plans,
  elements, rooms, apartments, counts, and where they apply tables and conflicts). The pipeline writes the same
  shape and is scored against it before any question is asked.
- Part 2, answering: every dataset question about those drawings, in all languages. The answerer reads the
  Part 1 gold instead of the drawing, so reading errors are taken out and a miss is an answering error.

`select-plans` picks the files and writes both parts to `data/stoa/golden/v2/`, with a manifest that records the
parameters, the split it came from and the sha256 of every file. The picks are seeded and deterministic:

- 40 CubiCasa5K sheets (30 dev, 10 eval), dealt over sheets with one plan and with several (from the "How many
  floors" answer, never from annotations).
- 30 swiss_dwellings plans (22/8), each as PDF and as PNG, because the two have different page frames.
- 15 ifc_models sheets (11/4), every model once before any model twice. IFC model files are not drawings, so their
  questions stay out.
- Up to 10 opening_design sheets (8/2). Only 3 have questions, and all 3 are in.

The v1 golden set (source x type x language cells, 4 questions each) still exists and can be scored with
`--golden`, but v2 is the one we report.

### Scale cases

Bogdan, 2026-11-13 22:31: "print rooms with areas, calculate it from dimension lines, from the scale, and those
with nothing say no scale and those who say no scale the rsult should be not to scale". Every gold file has a scale
object, and its evidence puts it in one of five cases: a scale text or bar, printed areas only, dimension lines
only, nothing usable printed, or a note saying the sheet is not to scale. After the plan picks, more files join
until each case has 10 dev and 3 eval files where the gold has them. The CubiCasa eval split has no gold, so most
cases have no eval files.

Bogdan, 23:33: "We should have ON ALL IMAGES THE SCALE TO GET THE AREA, BY APROXIMATING IT IN DIFFERENT WAYS IF NOT
GOOD SCALE ETC." So every image in golden v2 has a scale value. A sheet with no usable printed evidence gets an
`estimated` scale, approximated in at least two ways where possible (the CubiCasa5K annotation unit, door widths
against 0.80 m, a person's measurement), with its uncertainty and the methods named. A sheet that says it is not to
scale keeps that status and still carries an approximate value. Every room with an outline gets an area: `exact`
when the sheet prints it, otherwise `estimated` (outline times scale, with an uncertainty). `select-plans` refuses
gold that falls short of this, apart from schedule sheets, which have no plan to measure.

### The conflict slice

On 2026-11-13 at 23:05 Bogdan asked whether conflicts belong in the golden corpus and where they fit in the
pipeline. The answer he got: yes, as a small slice outside the headline. A conflict is found at ingestion stage 8
([PIPELINE.md](PIPELINE.md)), where a second, independent method measures a quantity the first one already
measured (a printed room area against the outline times the scale, a column count in the IFC model against what
the plan cut draws). When the two disagree, both values are kept.

The conflict gold (`data/stoa/extraction_gold/_conflicts/conflicts.jsonl`, written by review-10) lists, per file,
the quantities two methods measured. A `conflict` entry is a real disagreement that somebody looked at on the
drawing, never a measuring slip of ours. An `agree` entry is a quantity where both methods match, and it is there
to count false alarms. Every file in it joins v2 after the plan and scale picks, so the slice never changes which
other files are picked, and its entries are merged into the copied gold file. A file that is in v2 only for the
slice is scored only there: it is not a scale case, it stays out of the Part 1 headline, and its questions stay out
of Part 2. Without that rule the slice would have added 2,276 questions, 1,738 of them about IFC sheets, and runs
before and after it could not be compared (orchestrator's decision, 2026-11-13 23:29). The conflict questions among
the extras cover the answering side.

### Schedules

The opening_design sheets are mostly schedules. Their gold (review-8) lists the door, window, finish and keynote
tables row by row. A pure schedule sheet has `truth: "tables"`: only its tables are scored, and it is not a scale
case. The restroom sheet is a drawing and has element gold for its fixtures.

### Extras: questions Stoa didn't write

Bogdan, 2026-11-13 23:03, accepted. `part2_answering/extras.jsonl` holds hand-made questions on dev files:

- Paraphrases of dataset questions (reworded, restructured, with a typo, a hint dropped), with the same answer.
  They test that the answering doesn't depend on the template's exact wording.
- Unanswerable questions: an area on a plan without any scale, a fact no plan shows (ceiling height, year, owner),
  an element the drawing type can't show. The right behaviour is to abstain.
- Conflict questions about a quantity in the conflict slice. The right answer gives the resolved value and shows
  both measured values.

Review-7 writes the first two kinds into the file directly (ids 1000001-1000999). Review-10 writes its conflict
lines to `_conflicts/extras.jsonl` (ids 1001001-1001999), and `select-plans` merges them in by id.

## Scoring

### Part 1

Files pair by name, and a gold file is scored on what its `truth` covers. Elements and rooms match one-to-one on
the same page at IoU 0.5 or more (polygons where both sides have one), and give precision, recall and F1 per
class. Rooms are also scored on type and on area: within 2% where the gold area is exact (the swiss and IFC areas,
and areas printed on CubiCasa sheets). Plans are scored on the exact count, counts per class and file on an exact
match, which is what the count questions need. Scale gets a confusion table of gold status against predicted status
per case and `m_per_unit` within 2% for scaled gold. On a sheet whose gold scale is estimated, the prediction must
say `estimated` too: claiming a measured scale there is wrong. These are the headline numbers of Part 1. Estimated
gold values are not pass/fail: an estimated scale or room area is reported as the median relative error of the
prediction and the shares within 10% and 20%, per source.

Two sections follow the headline without changing it. Tables: a table is found by title or box overlap, rows pair
by the key column, columns pair by position, and the report gives tables found, row recall, row precision and
cell accuracy. Conflicts: per quantity, recall of the gold conflicts, false alarms on the gold `agree` entries, and
predicted conflicts that gold didn't check, which are reported but not judged.

### Part 2

Counts must be exact; areas, lengths and volumes within 2% in the question's unit (only m/ft and m2/ft2 are
converted). Text answers match after normalising and are also listed for a person to review, because Stoa scores
them free-form. A missing answer is wrong. The headline is the accuracy over the Part 2 questions, with numbers per
source and type, per split, evidence coverage (share of questions with a box), cost and latency.

The extras and the answer_v1.1 fields are scored as separate slices. A paraphrase is judged like any question, and
the report gives the gap to its origin questions. An unanswerable question passes only with `abstain: true`. A
conflict question passes when both values appear in the answer's `conflicts` and the answer is right. When answers
carry `confidence` or `abstain`, the report adds the abstain rate, the accuracy of abstained and other answers
(judging the best estimate, which `answer` still carries), and a calibration table of confidence buckets 0.2 wide
against accuracy.

### Where a wrong answer comes from

Run the answerer twice on the same questions, once on the gold extraction (`--reads gold-extraction`) and once on
the pipeline's own (`--reads pipeline-extraction`). Wrong both times: the answering is wrong. Right on gold and
wrong on the pipeline's: the extraction is wrong, and the file's entry in the Part 1 score shows which counts were
off and what happened to the scale. Right on the pipeline's and wrong on gold: check the gold and the dataset
answer.

### Baselines

`oracle` gives the gold back: the gold extractions for Part 1, the golden answers for Part 2 with confidence 1, an
abstention on every unanswerable extra and both values on every conflict extra. It must score 100% everywhere;
anything less is a scorer bug. `empty` (Part 1: nothing found, no scale) and `constant` (Part 2: the typical answer
per template from dev questions outside the golden set) are the floors a real method has to beat.

## Run history

Bogdan, 2026-11-13 ~22:48: "also make sure all the runs of the golden dataset, will be saved somewhere so at the
end we will be able to show the improvement". Every scored run against golden or dev is recorded as one file in
`eval/results/runs/`, so pull requests from different people never touch the same file. A record holds the time,
the commit, the method name, what was scored, and aggregate numbers only (including the table, conflict, extras and
calibration sections), never question text, answers or file names, because the repo is public. The full score
stays in the gitignored `data/stoa/golden/runs/`. `history --progress` shows each method's first, latest and best
numbers.

## What the answer should show

An answer line (answer_v1.1) carries the value and unit, evidence boxes on the drawing, the method, cost and
latency, and optionally a confidence, an abstain flag with the best estimate kept, the conflicting values with the
rule that resolved them, a short explanation, the regions deliberately left out with a reason, and the files read.
What a verifier should see, per kind of answer:

- counted elements outlined and numbered on the drawing, one colour per class;
- summed polygons filled with their values, and the sum;
- excluded items greyed, each with its reason;
- for facts only an IFC model holds, the element list with GlobalIds and the storey table;
- for schedules, the highlighted rows and the arithmetic;
- the licence credit under every image.

## Not built yet

- An evidence hit rate: the share of evidence boxes that overlap a true element of the asked class (IoU 0.3 or
  more) and the share of true elements boxed, where true positions are known (swiss DXF, IFC SVG tags, CubiCasa5K
  polygons). Elements drawn twice at the same place count once there. This would turn "verifiable" into a number.
- Free-text scoring without an LLM for ifc_bench and the opening_design text questions: each golden text item keeps
  a list of the quantities it asks for, and an answer passes when every one is matched (counts exact, measures
  within 2%) and enough of the key names appear. Review-7 has a prototype. v2 has no ifc_bench files.
- Per-item labels (`trust`: verified, rule, suspect, unverified; `profile`: answerable from the file itself or
  needing a sibling file; trap tags), and a dataset-weighted headline next to macro accuracy over families.
- A hand-made set for building-code checks, which the dataset has no questions for.
