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
