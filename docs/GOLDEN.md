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

The file set is frozen (orchestrator, 2026-11-13 23:48): every recorded run compares against the same files, so
better gold must not reshuffle them. v2 is rebuilt with `select-plans --keep data/stoa/golden/v2/manifest.json`,
which keeps every file of that build with its split and stratum and recomputes only the conflict slice and the
scale-case labels. Without `--keep`, the estimated scales of 2026-11-13 would have dropped the 16 sheets that joined
as scale cases (286 questions).

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
gold that falls short of this, apart from schedule sheets, which have no plan to measure. On the frozen set the
labels come from the current gold, so the sheets with nothing usable printed are now cases where the estimated
scale is what gets scored (the case is still called `nothing`).

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
- Unanswerable questions: a fact no plan shows (ceiling height, year, owner), an element the drawing type can't
  show. The right behaviour is to abstain.
- Estimate questions: an area or length on a sheet whose only scale is estimated (until 23:48 these were
  unanswerable; Bogdan, 22:33: "we should say that it's an estimation with computed from best effort"). The right
  answer is the gold value within 20%, labelled `estimate: true`. On a not-to-scale sheet the same, and the line's
  `why` quotes the sheet's note.
- Conflict questions about a quantity in the conflict slice. The right answer gives the resolved value and shows
  both measured values.

Review-7 writes the paraphrase, unanswerable and estimate lines into the file directly (ids 1000001-1000999). Review-10 writes its conflict
lines to `_conflicts/extras.jsonl` (ids 1001001-1001999), and `select-plans` merges them in by id.

### Text claims

D52 (review-7's proposal, accepted 2026-11-13; built in golden-8): `part2_answering/text_claims.jsonl` says, per
golden free-text question, what a right answer states. One line per question id, schema
`eval/schemas/text_claims_v1.schema.json`:

`{"id": 1234, "numbers": [{"value": 2, "unit": "count", "what": "rooms"}, {"value": 980, "unit": "ft2"}], "names": [{"name": "F9", "aliases": ["sealed concrete"]}], "by": "review-8", "note": null}`

`numbers` are quantities in any of count, m, cm, mm, ft, in, m2, ft2, min, h; `names` are names, codes or phrases,
each with optional aliases. A line needs at least one claim, and `by` says who curated it. A number that only
identifies something (a hardware group, a room number) is a name, not a number. The file sits next to
`questions.jsonl`, like `extras.jsonl`; the curator writes it directly and `select-plans` leaves it alone. On
2026-11-14 it holds drafts for the 13 dev text questions, made from their gold answers only (`by: "golden (draft
from the gold answer)"`); review-8 checks them against the sheets and adds the 3 holdout ones.
Record 0002 has the format as an amendment (2026-11-14 00:31): gold makers write the file, holdout lines
included, and builders never read it.

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
prediction and the shares within 10% and 20%, per source. A prediction may list in `read` the classes it looked
for (golden-7f); a class it left out is still scored as misses, and the table marks it `not read`. A sheet of
a BIM model may carry `model_objects`, every object of the model drawn or not (formats v1.2, 0004 amendment of
2026-11-14); Part 1 doesn't score it, and gold has none.

Two sections follow the headline without changing it. Tables: a table is found by title or box overlap, rows pair
by the key column, columns pair by position, and the report gives tables found, row recall, row precision and
cell accuracy. Conflicts: per quantity, recall of the gold conflicts, false alarms on the gold `agree` entries, and
predicted conflicts that gold didn't check, which are reported but not judged.

### Part 2

Counts must be exact; areas, lengths and volumes within 2% in the question's unit (only m/ft and m2/ft2 are
converted). Text answers match after normalising and are also listed for a person to review, because Stoa scores
them free-form. A missing answer is wrong. The headline is the accuracy over the Part 2 questions, with numbers per
source and type, per split, evidence coverage (share of questions with a box), cost and latency.

Two more lines follow the headline without changing it (golden-8).

Text by claims: a text question with a claims line passes when the answer states every claimed number and contains
every claimed name. Numbers are read with their units (6'-2 1/2", 8 ft 3 in, 41 1/2", 2318 SF, 2.35 m, 45 MIN.,
bare whole numbers and number words as counts); a number glued to letters or a hyphen is a code (D7, ST-4, 204.C).
They are converted to metres, square metres or minutes and matched one to one, counts exactly and measures within
2%. Names match as whole words after casefolding and replacing punctuation with spaces. Extra numbers in the answer
are reported, not penalised. The report gives the pass rate (dev and holdout), the share of number and name claims
met, and how many text questions have no claims yet.

Evidence hit rate: for each numeric question on a file whose gold has truth `elements`, the question's wording
gives its subject (an element class, a room type, the rooms with a label, number or name, an apartment's indoor
rooms, the numbered indoor rooms, all rooms, the plans; a sauna question means the sauna stoves, which is what the
dataset counts), and the subject picks the gold items. On v2 the picked items number the answer of every count
question and sum to the answer of every room-area question. An evidence box hits an item when it is on the same file
and page and its centre lies in the item's gold box. Precision is the share of evidence boxes that hit, recall the
share of items some box hits, both pooled per source and per source and subject. The centre rule, not IoU: thin
items (walls, windows) fail IoU on sub-percent offsets, one box can only point at what its centre lies on, and IFC
gold polygons are single drawn fragments, so boxes are compared on both sides. Not scored, and counted by reason:
text questions, files with truth `counts` or `tables`, apartment counts (an apartment has no box), questions about a
whole IFC model, and wordings the rules don't know (none on v2 or on the dev gold).

The extras and the answer_v1.1 fields are scored as separate slices. A paraphrase is judged like any question, and
the report gives the gap to its origin questions. An unanswerable question passes only with `abstain: true`. A
conflict question passes when both values appear in the answer's `conflicts` and the answer is right. An estimate
question passes when the value is within the line's tolerance (20%) and the answer says `estimate: true`. When answers
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

`oracle` gives the gold back: the gold extractions for Part 1, the golden answers for Part 2 with confidence 1 and
one evidence box per gold item the question is about, an abstention on every unanswerable extra and both values on
every conflict extra. It must score 100% everywhere;
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

### The pipeline series

`pipeline` is the product end to end on golden v2: Part 1 read from the drawings, Part 2 answered from that
extraction, every real adapter of the commit turned on. Each point runs from a clean export of a merge commit, not
the shared tree, by `eval/pipeline-run.sh <commit> [NAME=VALUE ...]` and scored by the same eval on the frozen
set, so the numbers compare. Its records say `dirty: false` with that commit, the settings it ran with, and the
scorer as `eval_commit`. `python -m stoa_eval series` prints this table (backfilled 2026-11-14 00:40-00:41; bdfae08 recorded 01:44; 5331dab recorded 05:02):

| commit | code time | settings that change | P1 element F1 cubi | P1 element F1 ifc | P1 element F1 open | P1 element F1 swiss | P2 accuracy | P2 dev | P2 holdout | abstained |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0f9120f | 2026-11-13 23:24 | extractor_bim=hello extractor_raster=hello extractor_vector=hello question_parser=hello second_counter=hello | 0.0% | 0.0% | 0.0% | 0.0% | 0/2948 (0.0%) | 0.0% | 0.0% | n/a |
| 85d3470 | 2026-11-13 23:55 | extractor_bim=hello extractor_raster=hello extractor_vector=pdf question_parser=templates second_counter=hello | 0.0% | 80.4% | 0.0% | 100.0% | 1262/2948 (42.8%) | 39.9% | 55.4% | 14.3% |
| 6e9a2df | 2026-11-14 00:39 | answer_prior=dev extractor_bim=hello extractor_raster=hello extractor_vector=pdf question_parser=templates second_counter=pdf | 0.0% | 80.4% | 0.0% | 100.0% | 2109/2948 (71.5%) | 71.1% † | 73.2% | 50.8% |
| bdfae08 | 2026-11-14 01:43 | answer_prior=dev extractor_bim=ifc extractor_raster=hello extractor_vector=pdf question_parser=templates second_counter=ifc | 0.0% | 100.0% | 0.0% | 100.0% | 2201/2948 (74.7%) | 73.4% † | 80.0% | 47.7% |
| 5331dab | 2026-11-14 04:56 | answer_policy=sha256:e3b0c44298fc answer_prior=dev credit_dataset=sha256:8943873073fb credit_photos=sha256:707a4bc6bf72 decisions_cache_dir=sha256:97d173a8f3a7 decisions_confidence=False decisions_kind=False decisions_timeout_s=30.0 extractor_bim=ifc extractor_raster=composite extractor_vector=pdf gemini_api_key=sha256:6e9ba2d4743b gemini_cache_dir=sha256:1aadd8ef582d gemini_model=gemini-3.5-flash gemini_timeout_s=60.0 projects_dir=sha256:c7690527b5a5 question_parser=templates raster_components=sha256:c0dec542627d rectifier=none region_model_dir=sha256:4b197e641e7f sample_archive=sha256:06aa07bd7490 second_counter=ifc tables=pdf verda_inference_api_key=sha256:e3b0c44298fc verda_reader_max_in_flight=4 verda_reader_url=sha256:e3b0c44298fc | 85.4% | 100.0% | 0.0% | 100.0% | 2701/2948 (91.6%) | 91.3% † | 92.9% | 1.0% |

Code time is the commit time (Europe/Helsinki); `*` marks a run recorded with uncommitted changes, timed when recorded. Abstained: share of golden answers marked `abstain` (n/a: no answer_v1.1 fields).

† In-sample: with answer_prior=dev an abstained answer carries the dev prior's value, and the prior is fit on dev.jsonl, which holds the golden dev questions. The holdout column is the honest number for the prior.

Settings the same at every point: extractor_cad=hello, log_level=INFO.

At 6e9a2df the answers the pipeline read itself are 1436 of 1450 right (99.0%); the other 1498 abstain and carry the
dev prior, 673 of them right (44.9%). Part 1 is the same at 85d3470 and 6e9a2df (same extractor). At bdfae08 (IFC reader) every answer that does not abstain is right (1542 of
1542); ifc_models Part 1 is 1630 of 1630 and Part 2 466 of 466. CubiCasa raster is unread up to bdfae08.

5331dab (integ, 2026-11-14 05:02) is the first point that reads CubiCasa raster: the val-chosen runtime config,
`RASTER_COMPONENTS=elements=decisions-s1536:region:C-yolo26s-1536,plans=decisions-s1536:region:C-yolo26s-1536,rooms=exp:ocr/G4-regpred-golden`
(the 1536 px detector with the region filter, Gemini Decisions' S1536 count swap from cached replies). The rooms
came from the precomputed `exp:ocr/G4-regpred-golden` (cached Gemini replies), not a runtime source; the record's
note says so. CubiCasa count 1124 of 1342 (bdfae08: 656). The record is public, so since 5331dab
`pipeline-record.sh` keeps a setting whose value the record's rule refuses (a path, a long `raster_components`)
as `name=sha256:<12 hex>`, and puts the given NAME=VALUE pairs verbatim in the run's note.

## Experiments (CubiCasa raster, 2026-11-14)

Bogdan, 2026-11-14: "Each should do a/b testing". The experiment tracks (detectors, segmentation, OCR, VLMs)
compare arms on their own split of CubiCasa, never on golden v2 or the sealed eval split. The commands are in
[eval/README.md](../eval/README.md).

`stoa_eval exp-split` writes the split to `data/stoa/exp/split.json`. It takes the 3,828 CubiCasa images with dev
questions, leaves out the 69 golden v2 dev files, and cuts the rest by drawing group into train (3,007 images), val
(376) and test (376). The cut is seeded, so a rerun writes the same file. Each part's questions are in
`data/stoa/exp/<part>_questions.jsonl`. Models train on train and are tuned on val; test is run once, for the arm
we ship.

`stoa_eval ab --a <arm> --b <arm>` answers the part's questions from each arm's extraction_v1 files with the
backend's own parser and takeoff, and judges them by Stoa's rule. An image the arm has no file for counts as
wrong. The image is the unit: B wins only when the 95% bootstrap interval of B minus A excludes 0. The report
also gives an exact McNemar p, but it counts questions, and the English and Finnish questions on one image are
not independent, so that p is overconfident and is not evidence on its own. There are three reference arms: `gold` (the dev gold extraction), `prior`
(the answer prior refit on train questions only) and `none` (nothing found). On val, gold answers 100.0% of the
questions and the prior 55.9%.

`stoa_eval gate --arm <arm>` is the confidence gate (E5). It compares three confidence signals: the mean of the
top 3 detection scores, the probability of the modal count from calibrated scores, and agreement with a second
arm. On val it picks a threshold per question family by Learn-then-Test, aiming at 95% exact among the answers
marked sure, with delta 0.05 split over the families (Bonferroni). The val numbers only pick thresholds; the
certificate comes from test. Test is run once for the arm we ship (`--certify`, recorded in
`data/stoa/exp/test-certified.json`; a second run of the same arm needs a written reason). The plan is the unit:
a plan marked sure counts as exact when every sure answer on it is. The result is always one sentence: "of the
plans marked sure, at least X% have every sure answer exact (N plans, 95% bound); the gate opens on Y% of plans".
Other signals plug in as files (`--signal-file`, gate_signal_v1). `--g1main` adds `g1main`, Gemini's probability
for the answered count, which is what the backend computes at runtime (DECISIONS_CONFIDENCE), from decide's cached
replies. `--family-arm 'room:*=<arm>'` answers some families from another arm, so the gate runs on the
combination the product actually uses. `--pool` sets one threshold per family group (elements, plans, rooms) instead:
on val, the loosest whose 95% Clopper-Pearson bound on the plans meets the target, then tightened until all groups
together meet it, because the certificate counts a plan wrong when any of its sure answers is. Every val number is
printed as "chosen on val, not a guarantee".

`stoa_eval gate-policy --gate data/stoa/exp/ab/gate-<arm>-val.json` writes `data/stoa/exp/gate.json`
(gate_policy_v1), the file the backend reads to mark answers sure:

```json
{"schema": "gate_policy_v1", "generated": "2026-11-14T05:02:02+02:00", "part": "val",
 "split_sha256": "<sha256 of data/stoa/exp/split.json>", "arm": "decide-S1536+ocr-G4", "second": null,
 "family_arms": {"room:kitchen": "ocr/G4", "...": "ocr/G4"}, "target": 0.95,
 "source": "data/stoa/exp/ab/gate-decide-S1536+ocr-G4-val.json", "certified": false,
 "families": {"plan": {"signal": "g1main", "threshold": 0.0144, "group": "plans",
   "val": {"note": "chosen on val, not a guarantee", "answers": 188, "sure": 188, "exact": 186,
           "coverage": 1.0, "bound": 0.967}}}}
```

An answer is sure when its family is listed and its `signal` is at or above `threshold`. Only families whose gate
opens and marks at least one val answer sure are listed. `split_sha256` is required (the loader refuses a file
without it). `certified` stays false until the one test run; `arm` (with `family_arms`) is what the thresholds
were set on, so a product that answers a family with another arm uses an untested threshold there.

The current file (2026-11-14, golden-17) is set by `stoa_eval gate-refit` on the demo config
(`tools/qa-env.sh config`): region:C-yolo26s-1536's val output with the backend's S1536 swap (frozen thresholds)
for elements and plans, regionrooms rooms (`ocr/G4-regpred`), signal g1main. The golden-16 file (decide's
cross-fit `decide/S1536`, `ocr/G4` rooms) gave the same gate. On val only plans open: elements and rooms stay shut, because Gemini is at least 0.95 sure of a few wrong counts (a toilet count,
G4 kitchen, bedroom and balcony counts), and with the plan as the unit the 95% bound needs about 60 plans per
error. The earlier file, set on detector C-yolo26s-v8 alone, also opened elements (0.7625) and sauna (0.664);
those thresholds were never valid for the arms the product answers with.

When the runtime config changes (a new detector), `uv run python -m stoa_eval gate-refit --detector <its val
output>` refits gate.json in one command (eval/README.md). Then, once, at the freeze, the test certificate:
`gate --part test --certify` with the same arm, swap, rooms and `--g1main` replies for the test images (decide
holds val and golden replies only, so that run needs G1main calls on test: spend, the orchestrator's OK).

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

- Evidence for apartment counts and for whole-model IFC questions, and evidence on the dev split outside golden v2
  (the dev extraction gold would allow it).
- Text claims for ifc_bench, which v2 has no files of.
- Per-item labels (`trust`: verified, rule, suspect, unverified; `profile`: answerable from the file itself or
  needing a sibling file; trap tags), and a dataset-weighted headline next to macro accuracy over families.
- A hand-made set for building-code checks, which the dataset has no questions for.
