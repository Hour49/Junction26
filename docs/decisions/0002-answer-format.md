# 0002: Our system writes one answer_v1 JSON line per question, and eval/ scores it

- Status: accepted for v1
- Date: 2026-11-13 20:13 (Europe/Helsinki)
- Decided by: agent golden (worker), approved by Bogdan's orchestrator (commit df04495, PR #16)
- Board thread: to be posted by the orchestrator

## Context

Stoa judges answers to questions about drawings and BIM models on accuracy, on showing a human where the answer came
from, on creativity and on low inference cost, 25% each (board #14). The dataset's `questions.jsonl` has the golden
answers; counts must be exact, areas, lengths and volumes within 2%. The system that answers and the scorer in
`eval/` have different owners, so the file between them needs a fixed shape.

## Decision

The contract is [eval/schemas/answer_v1.schema.json](../../eval/schemas/answer_v1.schema.json), generated from
`Answer` in `eval/stoa_eval/models.py`. One line per question, for example:

`{"id": 1234, "answer": 12.5, "unit": "m2", "evidence": [{"file": "data/swiss_dwellings/x.pdf", "page": 1, "box": [0.1, 0.2, 0.3, 0.4]}], "method": "vision", "cost_usd": 0.002, "latency_s": 1.5}`

`id` is the question's 1-based line number in `questions.jsonl`. `evidence` (boxes as page fractions) is there for the
verifiability and visualisation criteria, `cost_usd` for the cost criterion, and `latency_s` so that speed is
measured next to cost. The system writes the file; `eval/` reads it (`python -m stoa_eval score`).
The scorer refuses a file with an invalid line (it names the file and line), an unknown key or a repeated id.
`answer: null` and a missing line both count as wrong. Scoring rules: [eval/README.md](../../eval/README.md).

## Alternatives considered

- Free text that the scorer parses for a number and unit: a parsing slip would count against the method.
- Evidence in pixels: they depend on the render resolution; page fractions work for any rendering.
- Cost per run instead of per answer: it hides which questions are expensive.

## Consequences

- The system answers in the golden unit. The scorer converts only m/ft and m2/ft2.
- Unknown keys are refused so that a typo fails loudly, which means any new field needs a new version.
- A change ships as `answer_v2.schema.json` with a record that supersedes this one. The scorer reads one version at a
  time. `eval/tests/test_models.py` fails when a committed schema no longer matches the models.
- Open until the golden-set spec decides: an optional `explanation` for the human; `excluded` regions with reasons
  (what was left out of a count and why); `polygon` evidence besides boxes; `inputs` (the files read); IFC GlobalIds
  as evidence, because an answer read from an IFC model has no page or box to cite.

## Amendment, 2026-11-13 23:30: answer_v1.1

- Decided by: Bogdan, 2026-11-13 23:03 ("1yes 2 yes 3 yes 4 yes", accepting decision 4 of the golden-set spec draft
  and board #26); the shapes pinned by his orchestrator (formats-v1-1 brief); written by agent golden (worker).

answer_v1.1 adds optional fields to the same schema file (`answer_v1.schema.json`, now titled `Answer_v1.1`). Every
answer_v1 line stays valid, so this is an amendment, not a new version: `confidence` (0 to 1), `abstain` (the
system is too unsure; `answer` still holds the best estimate, because Stoa scores `null` as wrong), `conflicts`
(two or more `{value, unit, method, file, page, box}`, with `page` and `box` null for a value read from an IFC
model) with `resolution` (text, only next to `conflicts`), `explanation`, `excluded` (`{file, page, box, reason}`)
and `inputs`. Evidence items may carry `polygon` (page fractions) and `global_id` (IFC). This settles the open list
in Consequences above, except evidence without a page or box: an evidence item still needs both.

None of the new fields changes the headline score. The scorer adds an abstain rate, accuracy on abstained and other
answers, and a calibration table (confidence buckets of 0.2) on the golden questions. It also scores the Part 2
extras (`extras_v1.schema.json`: paraphrases, unanswerable and conflict questions) as separate slices; an
unanswerable question passes only with `abstain: true`. Rules: [eval/README.md](../../eval/README.md), spec:
[docs/GOLDEN.md](../GOLDEN.md).

## Amendment, 2026-11-13 23:48: `estimate`

- Decided by: the orchestrator (golden-7e brief), from Bogdan's rules of 22:33 ("we should say that it's an
  estimation with computed from best effort") and 23:31 ("ON ALL IMAGES THE SCALE TO GET THE AREA, BY APROXIMATING
  IT ... IF NOT GOOD SCALE"); written by agent golden (worker).

answer_v1.1 gets one more optional field, `estimate` (bool): the value rests on an estimated scale or reading, and
`explanation` says from what. An area on a sheet whose only scale is estimated is therefore answerable, as a
labelled estimate, instead of a question to abstain on. The extras get a matching kind, `estimate`, with
`expect: {"answer": <gold value>, "tolerance": 0.2, "estimate": true}`; it passes when the value is within the
relative tolerance (units converted as for any answer) and the answer says `estimate: true`. It is its own slice,
outside the headline.

## Amendment, 2026-11-14 00:31: `text_claims_v1`

- Decided by: the orchestrator (golden-9 brief), on review-7's proposal D52 (accepted 2026-11-13); written by agent
  golden (worker).

The free-text questions get a second score next to exact match. A golden-owned file,
`part2_answering/text_claims.jsonl` (schema `eval/schemas/text_claims_v1.schema.json`), lists per text question
the numbers (value and unit) and names a right answer states. A text answer passes the claims score when it states
every claimed number (counts exact, measures within 2% after unit conversion) and contains every claimed name as
whole words. answer_v1 itself does not change: the answer stays a string, and the headline still scores text by
exact match. Gold makers write the claims file: review agents write the lines (holdout ones included, as for the
counts-only gold of the eval files). The system that answers, and the agents who build it, never read it. Rules:
[docs/GOLDEN.md](../GOLDEN.md) "Text claims".
