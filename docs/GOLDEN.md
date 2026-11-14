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

### The hard slice

The Carbon-first work (sheet kind, a Carbon reader, big-sheet tiles, the printed scale) needs sheets our
CubiCasa-trained readers were not made for: huge sheets, several plans on one sheet, colour or concept plans,
photos and hand-drawn plans, and drawings that look like plans but are not (MEP, structural, site, elevations).
The hard slice is those sheets, labelled by eye in `hard_set_v1` (`eval/stoa_eval/hard_scoring.py`): the sheet
kind in the sheet-kind step's own words, whether a floor plan is on the sheet, the printed scale, and for each
count family a range `[lo, hi]` or "cannot tell". It is not part of golden v2 and stays outside every headline.
`stoa_eval hard` scores kind accuracy, floor-plan recall and precision, the share of counts inside their range (a
refusal counts as a miss; "cannot tell" is left out), and the scale where one is printed. It reads a pipeline run of
`stoa_eval hard-questions` (`app.cli answer`) and lines a classifier writes (`hard_pred_v1`). The images stay in the
gitignored `data/inbox/`. Records hold aggregates only (`eval/results/hard/runs/`), and labels are committed only
for files whose licence allows it.

think-local froze the labels on 2026-11-14: 26 files, a second batch of 18, and 4 inbox sheets whose source isn't
recorded, 48 in all. 44 of them are public in `eval/results/hard/gold/hard-set-20261114.json`; the 4 inbox
sheets stay local. The rows scored on these labels are the records named "(final labels)". A row can combine
several runs (`--run` with its `--questions`, repeated), for example when a later batch was run separately.

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
scorer as `eval_commit`. `python -m stoa_eval series` prints this table (backfilled 2026-11-14 00:40-00:41; bdfae08 recorded 01:44; 5331dab recorded 05:02; 2e1c0b0 recorded 07:14; 5fa8464 recorded 08:20; bd2471f recorded 10:25; 6150709 recorded 17:27; 240e620 recorded 19:57; 030abbb recorded 2026-11-15 00:56):

| commit | code time | settings that change | P1 element F1 cubi | P1 element F1 ifc | P1 element F1 open | P1 element F1 swiss | P2 accuracy | P2 dev | P2 holdout | abstained |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0f9120f | 2026-11-13 23:24 | extractor_bim=hello extractor_raster=hello extractor_vector=hello question_parser=hello second_counter=hello | 0.0% | 0.0% | 0.0% | 0.0% | 0/2948 (0.0%) | 0.0% | 0.0% | n/a |
| 85d3470 | 2026-11-13 23:55 | extractor_bim=hello extractor_raster=hello extractor_vector=pdf question_parser=templates second_counter=hello | 0.0% | 80.4% | 0.0% | 100.0% | 1262/2948 (42.8%) | 39.9% | 55.4% | 14.3% |
| 6e9a2df | 2026-11-14 00:39 | answer_prior=dev extractor_bim=hello extractor_raster=hello extractor_vector=pdf question_parser=templates second_counter=pdf | 0.0% | 80.4% | 0.0% | 100.0% | 2109/2948 (71.5%) | 71.1% † | 73.2% | 50.8% |
| bdfae08 | 2026-11-14 01:43 | answer_prior=dev extractor_bim=ifc extractor_raster=hello extractor_vector=pdf question_parser=templates second_counter=ifc | 0.0% | 100.0% | 0.0% | 100.0% | 2201/2948 (74.7%) | 73.4% † | 80.0% | 47.7% |
| 5331dab | 2026-11-14 04:56 | answer_policy=sha256:e3b0c44298fc answer_prior=dev credit_dataset=sha256:8943873073fb credit_photos=sha256:707a4bc6bf72 decisions_cache_dir=sha256:97d173a8f3a7 decisions_confidence=False decisions_kind=False decisions_timeout_s=30.0 extractor_bim=ifc extractor_raster=composite extractor_vector=pdf gemini_api_key=sha256:6e9ba2d4743b gemini_cache_dir=sha256:1aadd8ef582d gemini_model=gemini-3.5-flash gemini_timeout_s=60.0 projects_dir=sha256:c7690527b5a5 question_parser=templates raster_components=sha256:c0dec542627d rectifier=none region_model_dir=sha256:4b197e641e7f sample_archive=sha256:06aa07bd7490 second_counter=ifc tables=pdf verda_inference_api_key=sha256:e3b0c44298fc verda_reader_max_in_flight=4 verda_reader_url=sha256:e3b0c44298fc | 85.4% | 100.0% | 0.0% | 100.0% | 2701/2948 (91.6%) | 91.3% † | 92.9% | 1.0% |
| 2e1c0b0 | 2026-11-14 06:58 | answer_policy=sha256:e3b0c44298fc answer_prior=dev credit_dataset=sha256:8943873073fb credit_photos=sha256:707a4bc6bf72 decisions_cache_dir=sha256:97d173a8f3a7 decisions_confidence=True decisions_kind=True decisions_timeout_s=30.0 extractor_bim=ifc extractor_raster=composite extractor_vector=pdf gemini_api_key=sha256:6e9ba2d4743b gemini_cache_dir=sha256:1aadd8ef582d gemini_model=gemini-3.5-flash gemini_timeout_s=60.0 projects_dir=sha256:c7690527b5a5 question_parser=templates raster_components=sha256:c0dec542627d raster_scale=priors rectifier=r3 region_model_dir=sha256:4b197e641e7f sample_archive=sha256:06aa07bd7490 second_counter=ifc tables=pdf verda_inference_api_key=sha256:e3b0c44298fc verda_reader_max_in_flight=4 verda_reader_url=sha256:e3b0c44298fc | 85.4% | 100.0% | 0.0% | 100.0% | 2701/2948 (91.6%) | 91.3% † | 92.9% | 1.0% |
| 5fa8464 | 2026-11-14 08:15 | answer_policy=sha256:e3b0c44298fc answer_prior=dev credit_dataset=sha256:8943873073fb credit_photos=sha256:707a4bc6bf72 decisions_cache_dir=sha256:97d173a8f3a7 decisions_confidence=True decisions_kind=True decisions_provider=gemini decisions_timeout_s=30.0 eu_vlm_api_key=sha256:e3b0c44298fc eu_vlm_base_url=sha256:8d629f3b12ac eu_vlm_model=sha256:466b8aaefcdc eu_vlm_timeout_s=300.0 extractor_bim=ifc extractor_raster=composite extractor_vector=pdf gemini_api_key=sha256:6e9ba2d4743b gemini_cache_dir=sha256:1aadd8ef582d gemini_model=gemini-3.5-flash gemini_timeout_s=60.0 kind_provider=gemini projects_dir=sha256:c7690527b5a5 question_parser=templates raster_components=sha256:4448f99e9eaa raster_photo_components=sha256:e3b0c44298fc raster_scale=priors rectifier=r3 region_model_dir=sha256:4b197e641e7f rooms_provider=gemini sample_archive=sha256:06aa07bd7490 second_counter=ifc tables=pdf verda_inference_api_key=sha256:e3b0c44298fc verda_reader_max_in_flight=4 verda_reader_url=sha256:e3b0c44298fc | 85.1% | 100.0% | 0.0% | 100.0% | 2709/2948 (91.9%) | 91.8% † | 92.5% | 1.0% |
| bd2471f | 2026-11-14 10:14 | answer_policy=sha256:98f4f54c1a84 answer_prior=dev credit_dataset=sha256:8943873073fb credit_photos=sha256:707a4bc6bf72 decisions_cache_dir=sha256:97d173a8f3a7 decisions_confidence=True decisions_kind=True decisions_provider=gemini decisions_timeout_s=30.0 eu_vlm_api_key=sha256:e3b0c44298fc eu_vlm_base_url=sha256:8d629f3b12ac eu_vlm_model=sha256:466b8aaefcdc eu_vlm_timeout_s=300.0 extractor_bim=ifc extractor_raster=composite extractor_vector=pdf gate_policy=sha256:56ca7d9c795f gemini_api_key=sha256:6e9ba2d4743b gemini_cache_dir=sha256:1aadd8ef582d gemini_model=gemini-3.5-flash gemini_timeout_s=60.0 kind_provider=gemini projects_dir=sha256:c7690527b5a5 question_parser=templates raster_components=sha256:4448f99e9eaa raster_photo_components=sha256:e3b0c44298fc raster_scale=priors rectifier=r3 region_model_dir=sha256:4b197e641e7f rooms_provider=gemini sample_archive=sha256:06aa07bd7490 second_counter=ifc tables=pdf verda_inference_api_key=sha256:e3b0c44298fc verda_reader_max_in_flight=4 verda_reader_url=sha256:e3b0c44298fc | 85.1% | 100.0% | 0.0% | 100.0% | 2717/2948 (92.2%) | 92.0% † | 92.9% | 4.5% |
| 6150709 | 2026-11-14 17:19 | answer_policy=sha256:98f4f54c1a84 answer_prior=dev app_commit=None arbiter_model_dir=sha256:7a53d77f1cb9 check_policy=sha256:54bedb4a54d5 credit_dataset=sha256:8943873073fb credit_photos=sha256:707a4bc6bf72 decisions_cache_dir=sha256:97d173a8f3a7 decisions_confidence=True decisions_kind=True decisions_provider=gemini decisions_timeout_s=30.0 double_check_readers=sha256:37dadcc2376f eu_vlm_api_key=sha256:e3b0c44298fc eu_vlm_base_url=sha256:8d629f3b12ac eu_vlm_model=sha256:466b8aaefcdc eu_vlm_timeout_s=300.0 extractor_bim=ifc extractor_raster=composite extractor_vector=pdf gate_policy=sha256:56ca7d9c795f gemini_api_key=sha256:6e9ba2d4743b gemini_budget_usd=None gemini_budget_usd_per_hour=None gemini_cache_dir=sha256:1aadd8ef582d gemini_model=gemini-3.5-flash gemini_timeout_s=60.0 kind_provider=gemini local_gates=sha256:252c9ad87829 projects_dir=sha256:c7690527b5a5 question_parser=templates raster_components=sha256:dfa194af91d8 raster_photo_components=sha256:e3b0c44298fc raster_scale=priors rectifier=r3 region_model_dir=sha256:4b197e641e7f room_policy=furniture rooms_provider=gemini rule_packs_dir=sha256:99cb266c8d3d sample_archive=sha256:06aa07bd7490 second_counter=ifc tables=pdf triage_classifier=off triage_describer=off triage_describer_cache_dir=sha256:c8d350be00c1 triage_judge=off verda_inference_api_key=sha256:e3b0c44298fc verda_reader_max_in_flight=4 verda_reader_url=sha256:e3b0c44298fc | 86.1% | 100.0% | 0.0% | 100.0% | 2746/2948 (93.1%) | 92.8% † | 94.8% | 3.8% |
| 240e620 | 2026-11-14 19:34 | answer_policy=sha256:98f4f54c1a84 answer_prior=dev app_commit=None arbiter_model_dir=sha256:7a53d77f1cb9 carbon_cache_dir=sha256:6abedd30bf57 carbon_levels=off carbon_reader=large carbon_timeout_s=120.0 check_policy=sha256:54bedb4a54d5 credit_dataset=sha256:8943873073fb credit_photos=sha256:707a4bc6bf72 decisions_cache_dir=sha256:97d173a8f3a7 decisions_confidence=True decisions_kind=True decisions_provider=gemini decisions_timeout_s=30.0 double_check_readers=sha256:37dadcc2376f eu_vlm_api_key=sha256:e3b0c44298fc eu_vlm_base_url=sha256:8d629f3b12ac eu_vlm_model=sha256:466b8aaefcdc eu_vlm_timeout_s=300.0 evidence_embedder_manifest=sha256:e32ef7a1979f evidence_scope=set_aside extractor_bim=ifc extractor_raster=composite extractor_vector=pdf gate_policy=sha256:56ca7d9c795f gemini_api_key=sha256:6e9ba2d4743b gemini_budget_usd=None gemini_budget_usd_per_hour=None gemini_cache_dir=sha256:1aadd8ef582d gemini_model=gemini-3.5-flash gemini_timeout_s=60.0 kind_provider=gemini laws_dir=sha256:1c7084feadfb local_gates=sha256:252c9ad87829 projects_dir=sha256:c7690527b5a5 question_parser=templates raster_components=sha256:dfa194af91d8 raster_photo_components=sha256:e3b0c44298fc raster_printed_scale=carbon raster_scale=priors raster_tiles=off rectifier=r3 region_model_dir=sha256:4b197e641e7f resolver=off resolver_cache_dir=sha256:a82c300352d7 resolver_model=gemini-4-carbon resolver_timeout_s=30.0 room_policy=furniture rooms_provider=gemini rule_packs_dir=sha256:42d68d13a7df sample_archive=sha256:06aa07bd7490 second_counter=ifc sheet_kind=off sheet_kind_cache_dir=sha256:3c1fc4ca6c86 sheet_kind_cut=0.9 sheet_kind_set_aside=True tables=pdf triage_classifier=off triage_describer=off triage_describer_cache_dir=sha256:c8d350be00c1 triage_judge=off verda_inference_api_key=sha256:e3b0c44298fc verda_reader_max_in_flight=4 verda_reader_url=sha256:e3b0c44298fc | 85.4% | 100.0% | 0.0% | 100.0% | 2749/2948 (93.2%) | 92.8% † | 95.0% | 3.8% |
| 030abbb | 2026-11-15 00:41 | agent_base_url=sha256:e42d6fd4c658 agent_max_steps=8 agent_model=gemini-4-hydrogen agent_price_cached_per_m=0.375 agent_price_in_per_m=1.5 agent_price_out_per_m=9.0 agent_thinking=low agent_turn_usd=0.1 answer_policy=sha256:98f4f54c1a84 answer_prior=dev app_commit=None arbiter_model_dir=sha256:7a53d77f1cb9 carbon_cache_dir=sha256:6abedd30bf57 carbon_levels=ladder carbon_reader=large carbon_timeout_s=120.0 chat_model=gemini check_policy=sha256:54bedb4a54d5 credit_dataset=sha256:8943873073fb credit_photos=sha256:707a4bc6bf72 decisions_cache_dir=sha256:97d173a8f3a7 decisions_confidence=True decisions_kind=True decisions_provider=gemini decisions_timeout_s=30.0 double_check_readers=sha256:37dadcc2376f eu_vlm_api_key=sha256:e3b0c44298fc eu_vlm_base_url=sha256:8d629f3b12ac eu_vlm_model=sha256:466b8aaefcdc eu_vlm_timeout_s=300.0 evidence_embedder_manifest=sha256:e32ef7a1979f evidence_scope=all_non_plan extractor_bim=ifc extractor_raster=composite extractor_vector=pdf gate_policy=sha256:56ca7d9c795f gemini_api_key=sha256:6e9ba2d4743b gemini_budget_usd=0.0 gemini_budget_usd_per_hour=None gemini_cache_dir=sha256:1aadd8ef582d gemini_model=gemini-3.5-flash gemini_timeout_s=60.0 ifc_facts=True ifc_facts_cache=sha256:e3b0c44298fc ingest_groups_in_flight=1 kind_provider=gemini laws_dir=sha256:172eb29551cb local_gates=sha256:252c9ad87829 model_3d=True model_3d_memory_mb=1500 model_3d_timeout_s=120.0 projects_dir=sha256:c7690527b5a5 question_parser=templates raster_components=sha256:dfa194af91d8 raster_photo_components=sha256:e3b0c44298fc raster_printed_scale=carbon raster_scale=priors raster_tiles=off rectifier=r3 region_model_dir=sha256:4b197e641e7f resolver=off resolver_cache_dir=sha256:a82c300352d7 resolver_model=gemini-4-carbon resolver_timeout_s=30.0 room_policy=furniture rooms_provider=gemini rule_packs_dir=sha256:bb11c1da2483 sample_archive=sha256:06aa07bd7490 scale_carbon_doors=off second_counter=ifc services_cache_dir=sha256:e85ebecc89b0 services_follow=off sheet_kind=carbon sheet_kind_cache_dir=sha256:3c1fc4ca6c86 sheet_kind_cut=0.9 sheet_kind_set_aside=False tables=pdf triage_classifier=off triage_describer=carbon triage_describer_cache_dir=sha256:c8d350be00c1 triage_judge=rules vector_fallback=off verda_inference_api_key=sha256:e3b0c44298fc verda_reader_max_in_flight=4 verda_reader_url=sha256:e3b0c44298fc | 86.3% | 100.0% | 0.0% | 100.0% | 2749/2948 (93.2%) | 92.8% † | 95.0% | 3.8% |

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

2e1c0b0 (golden, 2026-11-14 07:14) is the demo config after QA F1/F2 (#70-#91), from `tools/qa-env.sh config`:
the same detector and S1536 swap, `RECTIFIER=r3`, `DECISIONS_CONFIDENCE=true`, `DECISIONS_KIND=true`,
`RASTER_SCALE=priors`, with no API key (cached replies only, no spend). Rooms came from
`exp:ocr/G4-regpred-golden` as at 5331dab, because the demo's `rooms=regionrooms` reads Gemini at runtime and
the gemini-rooms cache holds only 9 of the 79 CubiCasa golden pages: run that way, the other 70 read no rooms
(HTTP 400 on the placeholder key) and the headline falls to 2605/2948 on room questions alone, a run condition,
not a code change. Against 5331dab, by cause:

- Headline 2701/2948, unchanged: no headline answer changed its value; Part 1 unchanged.
- `DECISIONS_CONFIDENCE=true` (config): 1342 raster answers now carry the raw g1main score in `confidence` (not
  scored; the API shows it as an uncalibrated signal).
- `RASTER_SCALE=priors` (#81, #82): 7 CubiCasa area extras are answered on an estimated scale (labelled
  `estimate`, ±8-16% stated) instead of refused: estimate extras 0/13 to 5/13 right, labelled 0/13 to 7/13.
- Typo parsing (#80, #83): 2 typo paraphrase extras gain a "read X as Y" note; same value, same pass/fail.
- Conflict wording (#78): 6 IFC conflict extras' rule text drops the dataset's name; same value, still pass.

5fa8464 (golden, 2026-11-14 08:20) is the first point with the demo's rooms read at runtime, and the first with
config C (#102): `tools/qa-env.sh config` as it is, `elements` and `plans` from
`decisions-s1536:detector:C-yolo26l`, `rooms=regionrooms`. **This is the runtime rooms number**: one Gemini read per
page (gemini-3.5-flash, thinking low) through the backend's own reader and its pixel-keyed cache
(`data/cache/gemini-rooms`, #75), the replies the demo reuses for these pages. The cache was filled by one real-key
run on 11b40a5 (70 pages read, 9 already cached, 0 failures, about 0.44 USD at answer's measured 0.0063 USD a page);
the recorded run had no key and took every reply from the cache. A page read again can give other rooms (R1-1-5),
so a re-read can move this number; the precomputed `exp:ocr/G4-regpred-golden` rows above are a separate set of
reads of the same pages. Against 2e1c0b0, by cause:

- Headline 2701 to 2709/2948 (dev 91.8% †, holdout 92.5%); no answer outside CubiCasa changed.
- Runtime rooms instead of the precomputed reads (a run on 11b40a5 with config A, not recorded): 2697, -4, room
  questions only: balcony 46 to 50/50, bedroom 72 to 74/84, bathroom 80 to 72/80, wc 72 to 70/74, kitchen 90/102
  either way (30 room answers changed value). Estimate extras 5/13 to 4/13 right.
- Config C's detector (11b40a5 to 5fa8464, same runtime rooms): +12: door 78 to 80/104, sink 120 to 126/150,
  toilet 134 to 140/154, window 72 to 70/154, shower+bathtub 116/142 either way (24 answers changed value), rooms
  identical. Part 1 CubiCasa element F1 85.4% to 85.1%. Estimate extras labelled 7/13 to 6/13.

bd2471f (golden, 2026-11-14 10:25; branch exp/policy) is config C with golden's answer policy: `tools/qa-env.sh
config` at that commit adds `ANSWER_POLICY=../eval/results/policy/policy-C-L-swap.json` and
`GATE_POLICY=../eval/results/gate/gate-C-L-swap.json` (PR #98). The policy sends CubiCasa kitchen counts to the
prior (1 kitchen): the train prior beat config C's readers on kitchens on both val halves, and the backend A/B on val
gives +0.35 pp [+0.12, +0.60]. No key, every reply from the caches, no spend. Against 5fa8464, by cause:

- Headline 2709 to 2717/2948 (dev 92.0% †, holdout 92.9%); Part 1 unchanged.
- `ANSWER_POLICY`: the 102 CubiCasa kitchen-count answers are now method `prior:policy`, 90 to 98 right (dev +6,
  holdout +2); no other answer changed value. Each one abstains with the prior's value, so abstained goes 1.0% to
  4.5%. The dev prior is fit on dev.jsonl, so the dev part of the gain is in-sample (†); the train prior gives the
  same value.
- `GATE_POLICY`: 286 answers marked sure, 585 not, the rest null; no policy answer is marked sure.

IFC gold with the reader's room words (golden, 2026-11-14 15:30; no series point recorded). #167 rebuilt the IFC
Part 1 gold with the room words the IFC reader uses. The old gold typed 408 of the 597 rooms in 24 dev IFC sheets
as `other` where the reader says hall (127), living (96), wc (81), bedroom (65), bathroom (18), kitchen (16) or
storage (5). The rebuild of golden v2 ran `select-plans --keep data/stoa/golden/v2/manifest.json`: files.jsonl,
questions.jsonl, extras.jsonl and text_claims.jsonl are byte-identical, and only those 24 gold files changed, in room
`type` only. One run of 872ebc3 at default settings, scored against the old and the new gold: ifc_models room type
accuracy goes from 65.2% to 100.0% and count exact from 93.7% to 100.0% (room:bathroom and kitchen were 86.7%;
bedroom, hall, living and other 80.0%; wc 93.3%). Nothing else moved. The series columns above (element F1, Part 2)
don't depend on room type and are unchanged. The earlier records' room type accuracy and IFC count numbers were
scored against the old words.

Swiss gold with the reader's room words (golden, 2026-11-14 about 15:00; no series point recorded). #184 types a lone
"Zimmer" (and "Pièce", "Stanza") as a bedroom on swiss plans, in the reader and in the swiss Part 1 gold. Golden v2
was rebuilt the same way, with `select-plans --keep`: files.jsonl, questions.jsonl, extras.jsonl and text_claims.jsonl
are byte-identical, and 58 swiss gold files changed (33 PDF, 25 PNG; 44 dev, 14 holdout), in room `type` only: 527
rooms go from `other` to `bedroom` (401 dev, 126 holdout). Main's reader at 4cfb1ce (one run at default settings)
against the old gold: swiss room type accuracy 74.4%, room:bedroom and room:other count exact 16.7%, overall count
exact 56.9%. Against the new gold: 100.0%, 100.0% and 60.6%, the same as before #184. Element F1 and Part 2
(1596/2948 at these settings) are the same against both.

6150709 (golden, 2026-11-14 17:27) is the shipped demo config on main after #240, from `tools/qa-env.sh config` at
that commit: config C1-T1 (the local count arbiter T1 picks the door, window, sink, toilet, shower and bathtub
counts; the other elements and the plans come from the eight-view detector behind the Decisions S1536 swap; rooms
from Gemini), the l1 and m1 double-check readers, the levels check policy with its local gates, and ROOM_POLICY at
its default (`furniture`). The run had no key and took every reply from the caches, so nothing was spent; all 79
CubiCasa pages have rooms, the count arbiter's reading and both readers. The CLI that runs golden does not apply
CHECK_POLICY or LOCAL_GATES (only the API does), so this point measures answer values, not the double-check or the
levels. A second run of the same export with bd2471f's config C (not recorded) splits the change. Against bd2471f,
by cause:

- Headline 2717 to 2746/2948 (dev 92.0% † to 92.8% †, holdout 92.9% to 94.8%).
- Code, with config C on both sides: +19, all on opening_design schedule questions. 19 questions that were refused
  (18 as unsupported, 1 as not in the drawing) are now answered from the schedules, 18 of them right: door counts 17
  to 27/27 (9 of the 10 were refused before, 1 was answered wrong), window counts 0 to 6/6, the room sum and maximum
  0 to 1/1 each, door reads 5 to 6/8. #122 and #123 are the only merges since bd2471f that touch the schedule code.
  Abstained goes from 4.5% to 3.8% for the same reason. The CubiCasa extraction is byte for byte the same.
- Config C to C1-T1, with the code of 6150709 on both sides: +10, on CubiCasa element counts only: shower+bathtub
  116 to 120/142, toilet 140 to 144/154, window 70 to 72/154; door (80/104) and sink (126/150) change some answers
  but not the totals. Dev +16, holdout -6. Part 1 CubiCasa element F1 85.1% to 86.1%. No answer outside CubiCasa
  changed.
- The IFC and swiss extraction files differ from bd2471f's in room types (the 408 IFC rooms of #167, the 527 swiss
  rooms of #184) and in new window fields on the IFC model objects. No Part 2 answer changed because of them.

240e620 (golden, 2026-11-14 19:57) is the shipped demo config on main after #280, from `tools/qa-env.sh config` at
that commit: 6150709's config plus the two Carbon settings of #277. `CARBON_READER=large` lets Gemini Carbon count
the things drawn on images over 4,000 px, while the shipped reader keeps the rooms, the scale and the double-check
(#269). `RASTER_PRINTED_SCALE=carbon` puts a printed scale in place of the estimate and sets printed counts against
the read ones (#256). The run had no key, so nothing was spent and every Carbon reply came from the cache. The two
golden CubiCasa images over 4,000 px (12949 and 9243, 4960 x 3507) have cached Carbon reads. The printed-scale call
had a cached reply on 14 of the 79 CubiCasa pages and failed on the other 65 (HTTP 400 without a key); with a key
those would be read too, at about 0.015 USD a sheet. Against 6150709, by cause:

- Headline 2746 to 2749/2948 (dev 92.8% † on both, holdout 94.8% to 95.0%). Five golden answers changed value.
  Routes are the same, and so is every IFC, swiss and opening_design extraction file.
- `CARBON_READER=large` (config): window counts on the two big images, dev only. 12949 goes from 17 to 12 (gold
  11, still wrong; the question, its Finnish twin and the paraphrase extra 1000001). 9243 goes from 13 to 14 (gold
  14, now right; the question and its Finnish twin). The other counts on those pages don't change. Part 1 CubiCasa
  element F1 goes from 86.1% to 85.4%, all on these two pages: door 90.7% to 88.3% (true positives 699 to 681),
  window 84.6% to 85.5%, sauna stove and shower one true positive fewer each. The door counts are the same, but
  Carbon's door boxes are about five times the size of the gold ones (mean 0.0029 against 0.00058 of the page) and
  overlap them with an IoU of 0.09 to 0.35, where the detector's reached 0.41 to 0.98, so they no longer match.
- `RASTER_PRINTED_SCALE=carbon` (config): no scale changed on the 14 pages it read. Two of them (282 and 6645)
  print room counts ("3H+K+S", "5H+K+S"), which are now stage-8 `room_count` conflicts for `room:kitchen`,
  `room:sauna` and all rooms. No answer changed. Eval refused those conflicts until this record's eval commit
  (decision 0004, amendment of 2026-11-14 19:57: a room type can be a conflict's class).
- Code: #273 answers a schedule read that names no row when every row agrees, so 89460 (a window size on A700,
  holdout) goes from refused to right. 89428 (the area of the two locker rooms) is still refused as unsupported.
  #280 (scanned PDFs) and the other merges since 6150709 change no golden answer.

030abbb (golden, 2026-11-15 00:56) is main after tonight's merges, in its own demo config (`tools/qa-env.sh config`
at that commit: 240e620's plus SHEET_KIND=carbon, SHEET_KIND_SET_ASIDE=false, CARBON_LEVELS=ladder, CHAT_MODEL,
IFC_FACTS, MODEL_3D, TRIAGE_DESCRIBER=carbon, TRIAGE_JUDGE=rules, EVIDENCE_SCOPE). No key, 0 USD; 58 Carbon
check calls (the ladder's) had no cached reply and were refused, which touches levels, not answers. Against 240e620:

- Headline unchanged, 2749/2948 (dev 92.8% †, holdout 95.0%); no golden answer changes value. 26 answer lines
  differ: 21 in `sure` only, 2 in evidence and `sure`, 3 explanations (two total-area extras now say they are the
  sum of the rooms the reader found, #350).
- Part 1: CubiCasa element F1 85.4% to 86.3%; CubiCasa room area within 2% 9/82 to 57/82 (printed m2 in the room
  label, #341); A-701's scale goes from no_scale to scaled (#340, a scanned PDF's ratio in page units).

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

`stoa_eval gate-policy --gate data/stoa/exp/ab/gate-<arm>-val.json [--certificate data/stoa/exp/ab/gate-<arm>-test.json]`
writes `data/stoa/exp/gate.json` (gate_policy_v1), the file the backend reads to mark answers sure:

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
without it). `certified` is false until the one test run of the same gate meets the target; that run is then
kept in `test` (its file and certificate). `arm` (with `family_arms`) is what the thresholds were set on, so a
product that answers a family with another arm uses an untested threshold there.

The current file (2026-11-14 08:25, golden-19) is config C's, the shipped demo config (#102,
`tools/qa-env.sh config`, which passes a frozen, committed copy:
`GATE_POLICY=../eval/results/gate/gate-C-L-swap.json`, so a refit changes the demo only with a commit). Arm
`ab/runtime-C-L-swap`: integ's runs of the whole config through the backend runtime, val
(`integ/val/C-L-swap`) and its single test run (`integ/test/C-L-swap`) linked into one folder so both name the
same arm; signal g1main from the backend's own Decisions caches (`integ/decisions-cache-val`, `-test`).

- Val (chosen on val, not a guarantee): plans open at 0.0144 (188 of 188 plans, 185 exact); elements (door,
  shower+bathtub, sink, toilet, window) at 0.771, after the union rule tightened them from 0.759 (119 sure plans,
  1 wrong); rooms stay shut. All groups together: 188 sure plans, 4 wrong, bound 95.2%.
- **Test (once, 08:25, no tuning after): of the plans marked sure, at least 96.2% have every sure answer exact**
  (374 of 376 plans sure, 366 exact; one-sided 95% bound). Per family on test: plan 372/374 exact, toilet
  222/224, sink 40/40, shower+bathtub 77/82, door and window 0 sure. `certified: true`.

Before config C, the file (golden-17) was set by `stoa_eval gate-refit` on the then demo config
(`tools/qa-env.sh config`): region:C-yolo26s-1536's val output with the backend's S1536 swap (frozen thresholds)
for elements and plans, regionrooms rooms (`ocr/G4-regpred`), signal g1main. The golden-16 file (decide's
cross-fit `decide/S1536`, `ocr/G4` rooms) gave the same gate. On val only plans open: elements and rooms stay shut, because Gemini is at least 0.95 sure of a few wrong counts (a toilet count,
G4 kitchen, bedroom and balcony counts), and with the plan as the unit the 95% bound needs about 60 plans per
error. The earlier file, set on detector C-yolo26s-v8 alone, also opened elements (0.7625) and sauna (0.664);
those thresholds were never valid for the arms the product answers with.

When the runtime config changes (a new detector), `uv run python -m stoa_eval gate-refit --detector <its val
output>` refits gate.json in one command (eval/README.md). Then, once, the test certificate: `gate --part test
--certify` with the same arm, swap, rooms and `--g1main` replies for the test images, and `gate-policy
--certificate` to put it in gate.json. A refit for another config starts uncertified again.

### The double-check policy (CHECK_POLICY)

The gate says which answers are sure; the double-check policy says which ones ask a person to look. Bogdan's goal
(D476, 2026-11-14): even at 92% overall accuracy, flag at least 95% of the wrong answers and ask for feedback on
them, never refuse. `stoa_eval check-policy --recall 0.96` fits it on val: each family's signal is turned into
P(wrong) by logistic regression, cross-fit on the val halves (on the logit when the signal is a probability;
families with fewer than 10 wrong answers share one calibration, `--pool-below 10`), and one P(wrong) cut over all
families flags at least 96% of val's wrong answers. The file holds one threshold per family on its signal
(check_policy_v1); `--always-flag` adds units flagged whatever their signal. Only signals the backend computes are
used: `g1main` (DECISIONS_CONFIDENCE) and local-dec's local gates (LOCAL_GATES). Routes are certified on golden v2's
holdout (vector and BIM yes, schedules no).

Levels (Bogdan, 2026-11-14: cut 0.20). `--medium 0.20` adds a second threshold per family, `medium`, read from the
same all-val calibration at P(wrong) 0.20: a certified answer is High, an answer at or above `medium` is Medium,
any other is Low. A calibration group whose cross-fit Medium has fewer than 30 answers or is under 80% exact gets
no Medium (`--medium-min-units`, `--medium-min-exact`; window on C1-T1, 7 answers). The top-level `levels` block
keeps the cross-fit counts per level. Each route gets a `level`: High when certified, else Medium when its golden
v2 dev answers reach 30 at 80% exact (schedules: 35/37), else Low. On C1-T1 val, cross-fit: High 44.9% of the
answers at 98.9% exact, Medium 34.6% at 91.6%, Low 20.4% at 58.6%. An always-flagged bedroom answer (a bedroom
with no printed label) is Low whatever its score, in eval and in the backend (orchestrator, 2026-11-14), so the
Medium figure is what was measured. A known small difference: eval does not model #174's plan agreement, so 3 val
plans the backend asks about count as High here.

The levels file is `eval/results/check/check-C1-T1-recall96-rt-full-small-medium20.json` (sha256
`bfce5524cd32f3a6aac94307265892ed99251bc1efbee692ba9855e8d11b369a`), made by `check-policy --medium 0.20` on the
pinned policy's inputs. Every field of the pinned file (sha256
`a9334da1b908866d57fb4066791011bf5344a0f11471a05dba2f0815dd239def`) has the same value in it, except `generated`;
it only adds `medium` per family, the `levels` block, and each route's `level` and `dev`. The pinned file stays
the policy the test certificate below was computed with.

The policy that ships (orchestrator, 2026-11-14) is `check-C1-T1-recall96-rt-full-small.json` (committed as
`eval/results/check/check-C1-T1-recall96-rt-full-small.json`, sha256
`a9334da1b908866d57fb4066791011bf5344a0f11471a05dba2f0815dd239def`), fit on config C1-T1's val answers: door, plan,
sauna and shower+bathtub on `lgate2-rt`, toilet on `lgate-rt-nol1`, the rest on `g1main`. Cross-fit on val: 55.1%
of the answers flagged, 96.0% of the wrong ones among them, 98.95% of the unflagged answers exact. The local gates
read the count arbiter's L1 probabilities and P and the double-check readers, so the config needs `arbiter-t1` in
RASTER_COMPONENTS and DOUBLE_CHECK_READERS `l1,m1`; on a drawing without them those families always ask.

Known limitation: the policy is fit on ROOM_POLICY=gold-labels (rooms typed by their printed label, as the
reference answers are), and the demo runs ROOM_POLICY=furniture (a room with a bed is a bedroom). Room families
are therefore certified outside the conditions they were fit on. The main case is covered by a rule: a bedroom
count that includes a bedroom with no printed label always asks. The test certificate is below.

#### The test certificate (config C1-T1)

The committed policy is the val fit, byte for byte; the test read changes nothing in it. The certificate is the
backend's own `ask()` with that policy on the drawings the test read stored, so it runs the same code as the API,
then each verdict is joined with the truth. integ read the 376 CubiCasa test pages once (2026-11-14 15:37-16:48,
commit 671d67f), with the shipping config (C1-T1 with the arbiter-t1 count arbiter run live, DOUBLE_CHECK_READERS
`l1,m1`, LOCAL_GATES, DECISIONS_CONFIDENCE, #174's plan agreement) and ROOM_POLICY=gold-labels, as on val. The
read covers the raster route only; the vector and BIM routes are certified on golden v2's holdout (above). The
two scripts are in `eval/certificate/`, byte for byte as they ran. From a backend checkout of the read's commit:

```bash
PYTHONPATH=. uv run --locked python ../eval/certificate/certify.py --drawings <run>/extraction/cubicasa5k --questions <run>/questions.jsonl --answers <run>/answers.jsonl --policy <check policy> --local-gates <lgate2-rt.json,lgate-rt-noL1.json> --flags <run>/flags --g1main <run>/g1main.json --out certified.jsonl --api-answers answers-api.jsonl
cd ../eval && PYTHONPATH=. uv run --locked python certificate/certify_join.py <test questions with truth> answers-api.jsonl certified.jsonl
```

An answer is flagged when the policy does not certify it, so it asks for a double-check. The numbers count
questions, as the join does. On val each page and family has one English and one Finnish question with the same
answer, so every count there is twice the number of answers; the 95% bound (one-sided Clopper-Pearson) is computed
on answers, not questions (on test too, every page and family has two questions with one answer and one verdict).

**On the test pages, the double-check flagged 97.0% of the wrong answers (one-sided 95% bound 95.3%) and asked on
62.1% of all answers; 99.0% of the answers it did not flag are exact.**

| read | rated | wrong | flagged | wrong flagged (recall) | 95% bound on recall | unflagged exact |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| val, shipped thresholds (as the backend runs) | 6764 | 800 | 3962 (58.6%) | 782/800 (97.8%) | 96.1% | 2784/2802 (99.36%) |
| val, cross-fit (each half under the other half's fit) | 6764 | 800 | 3730 (55.1%) | 768/800 (96.0%) | 94.0% | 3002/3034 (98.95%) |
| **test, once** | 6718 | 872 | 4174 (62.1%) | 846/872 (97.0%) | 95.3% | 2518/2544 (98.98%) |
| test, first run of the certificate (kitchen scored on the prior, see below) | 6718 | 858 | 3908 (58.2%) | 808/858 (94.2%) | 92.0% | 2760/2810 (98.22%) |

The val rows are chosen on val, not a guarantee: the shipped row is in-sample, and the cross-fit row is the honest
val estimate. The 96% target is one point above Bogdan's 95% (D476, D490), a margin for choosing the cut on val.

Per family (questions; val with the shipped thresholds):

| family | val flagged | val recall | val unflagged exact | test flagged | test recall | test unflagged exact |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| door | 100.0% | 152/152 | - | 100.0% | 142/142 | - |
| plan | 7.4% | 6/8 | 694/696 | 9.3% | 8/8 | 682/682 |
| room:balcony | 96.0% | 20/20 | 10/10 | 94.3% | 18/18 | 12/12 |
| room:bathroom | 48.9% | 24/24 | 186/186 | 52.4% | 40/40 | 178/178 |
| room:bedroom | 67.5% | 40/42 | 156/158 | 69.4% | 48/54 | 136/142 |
| room:kitchen | 44.9% | 38/42 | 288/292 | 51.6% | 38/40 | 248/250 |
| room:wc | 62.9% | 20/20 | 132/132 | 57.4% | 6/14 | 148/156 |
| sauna | 4.1% | 4/6 | 518/520 | 5.3% | 4/8 | 500/504 |
| shower+bathtub | 80.4% | 60/62 | 132/134 | 100.0% | 94/94 | - |
| sink | 90.0% | 68/68 | 74/74 | 90.8% | 86/86 | 68/68 |
| toilet | 20.0% | 14/20 | 594/600 | 26.6% | 30/36 | 546/552 |
| window | 100.0% | 336/336 | - | 100.0% | 332/332 | - |

Three notes on what this read does and does not cover:

- Kitchen (the certificate's first run, corrected). The test read answered through the CLI, where ANSWER_POLICY
  sends CubiCasa kitchen counts to the dev prior, because a page's path there is `data/cubicasa5k/...`. The API
  never does: an uploaded file keeps its bare name, so `source_of()` (`backend/app/core/answering/model.py:75`)
  finds no dataset, and the kitchen count comes from the drawing, scored by G1main (checked live on a val page
  at 671d67f: method takeoff, sure). The first run of the certificate took each answer's score from the run's
  line, and on kitchen that was the prior's hit rate (0.9579): all 516 kitchen answers were certified, 26 of
  them wrong, and the prior's value was judged. The corrected run (the test row) scores G1main's P of the
  drawing's count, as the API does, and judges the answer the API gives; only the 516 kitchen lines change (266
  of them now ask), and on every line answered from the drawing in both runs the two scores are equal (6,202 of
  6,202). The corrected run is the product's. The API's kitchen answers are 476/516 exact on test (92.2%; the
  prior's were 490/516), so the API's test accuracy is 5,846/6,718 (87.0%), not the CLI read's 5,860 (87.2%).

- Sauna. The count arbiter stores, in `count_arbiter["sauna"]`, T1's P for its own sauna-stove pick. C1-T1 does
  not answer sauna with that pick: the rule counts sauna rooms first (one per sauna room, else C1's stoves from
  the Decisions swap). lgate2-rt's sauna score therefore reads the arbiter's P next to an answered count that can
  differ from the arbiter's pick. The gate model and the policy were fit on exactly these values: on val C1-T1's
  sauna answer equals the arbiter arm's on 271 of 271 pages, and the arbiter's pick differs from the answer on 5 of
  them. Those 5 score 0.83 to 0.94, below the sauna threshold 0.971, so they ask (1 of the 5 is wrong): on val
  every sauna answer the arbiter did not back asked. On val 260 of 271 sauna answers are certified, 1 of them
  wrong.
- Photos. The test read answers through the CLI (`python -m app.cli answer`), which has no phone-photo
  rectifier and no reading flags: both run only in the API's ingest. The test pages are CubiCasa plan images
  (PNG scans of drawings), not phone photos, so neither the rectifier nor a photo flag would apply to them. In
  the API a flagged page (a phone photo or a scanned PDF) never certifies, and this certificate says nothing
  about photos.

#### Confidence levels on test (config C1-T1)

The levels are scored on the same read as the certificate. Each answer of the corrected run gets the level the
backend gives it (`ask()` with `check-C1-T1-recall96-rt-full-small-medium20.json`, PR #233), and is then joined
with the truth. This is the single read of the 376 test pages, not a second one. The rule and its thresholds
were written down with their sha256 on 2026-11-14 at 16:48:46, before any test number of the levels was computed,
and nothing was refit afterwards. The Medium thresholds in the committed file equal the pre-registered ones
(largest difference 2e-16). The counts are answers, one per page and family (3,359; each has an English and a
Finnish question with one verdict), with Wilson 95% intervals.

| level | test: share (answers) | test: exact | test: wrong | val cross-fit: share, exact |
| --- | ---: | ---: | ---: | ---: |
| High | 37.9% (1,272) | 99.0% [98.3, 99.4] | 13 | 44.9%, 98.9% |
| Medium | 41.1% (1,381) | 92.8% [91.3, 94.0] | 100 | 34.6%, 91.6% |
| Low | 21.0% (706) | 54.2% [50.6, 57.9] | 323 | 20.4%, 58.6% |

These levels are without Carbon. With `CARBON_LEVELS=ladder` (decision 0011, amendment 2026-11-14), a Medium
answer Gemini Carbon counts the same is High too (basis `carbon`), and High is no longer only the certified
answers: on 256 val pages it went from 99.0% to 97.7% exact (not measured on test). The 99% figures here hold for
basis `certified`.

Per family on test (share of the family's answers, their number, exact rate with its interval):

| family | answers | High | Medium | Low |
| --- | ---: | --- | --- | --- |
| door | 277 | 0 | 57.4% (159), 88.1% [82.1, 92.2] | 42.6% (118), 55.9% [46.9, 64.6] |
| plan | 376 | 90.7% (341), 100.0% [98.9, 100.0] | 8.0% (30), 93.3% [78.7, 98.2] | 1.3% (5), 60.0% [23.1, 88.2] |
| room:balcony | 106 | 5.7% (6), 100.0% [61.0, 100.0] | 87.7% (93), 93.5% [86.6, 97.0] | 6.6% (7), 57.1% [25.0, 84.2] |
| room:bathroom | 187 | 47.6% (89), 100.0% [95.9, 100.0] | 42.8% (80), 93.8% [86.2, 97.3] | 9.6% (18), 16.7% [5.8, 39.2] |
| room:bedroom | 232 | 30.6% (71), 95.8% [88.3, 98.6] | 50.0% (116), 92.2% [85.9, 95.9] | 19.4% (45), 66.7% [52.1, 78.6] |
| room:kitchen | 258 | 48.4% (125), 99.2% [95.6, 99.9] | 42.6% (110), 99.1% [95.0, 99.8] | 8.9% (23), 21.7% [9.7, 41.9] |
| room:wc | 183 | 42.6% (78), 94.9% [87.5, 98.0] | 53.6% (98), 98.0% [92.9, 99.4] | 3.8% (7), 85.7% [48.7, 97.4] |
| sauna | 266 | 94.7% (252), 99.2% [97.2, 99.8] | 3.8% (10), 90.0% [59.6, 98.2] | 1.5% (4), 75.0% [30.1, 95.4] |
| shower+bathtub | 351 | 0 | 83.2% (292), 94.5% [91.3, 96.6] | 16.8% (59), 47.5% [35.3, 60.0] |
| sink | 371 | 9.2% (34), 100.0% [89.8, 100.0] | 83.6% (310), 90.0% [86.2, 92.9] | 7.3% (27), 55.6% [37.3, 72.4] |
| toilet | 376 | 73.4% (276), 98.9% [96.9, 99.6] | 22.1% (83), 90.4% [82.1, 95.0] | 4.5% (17), 58.8% [36.0, 78.4] |
| window | 376 | 0 | 0 | 100.0% (376), 55.9% [50.8, 60.8] |
| **pooled** | 3,359 | 37.9% (1,272), 99.0% [98.3, 99.4] | 41.1% (1,381), 92.8% [91.3, 94.0] | 21.0% (706), 54.2% [50.6, 57.9] |

What the table shows:

- Medium and Low keep their val meaning on test: 92.8% against 91.6%, and 54.2% against 58.6%. Every family with
  30 or more Medium answers is between 88% and 99% exact.
- Fewer answers are High than on val: 37.9%, against 44.9% cross-fit and 41.4% with the shipped thresholds. No
  shower+bathtub answer is certified on test (19.6% of them on val with the shipped thresholds): its gate score
  tops out at 0.983 on this read, under the threshold 0.988.
- High is weakest on wc (74 of 78 exact) and bedroom (68 of 71). Low is mostly wrong on bathroom (3 of 18 exact)
  and kitchen (5 of 23). Every window answer is Low, and 55.9% of them are exact.
- No test answer was held for a check (the read uses ROOM_POLICY=gold-labels), and no page was flagged.
- The pre-registered rule gave window a Medium threshold; the committed file gives it none. That moves 2 window
  answers from Medium to Low and changes nothing else.
- The levels were first scored at 16:51 on the certificate's first run (kitchen from the prior, see the kitchen
  note above): High 41.8% at 98.2%, Medium 37.9% at 92.2%, Low 20.3% at 55.2%. The table above is the corrected
  run; only the kitchen lines differ.

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
