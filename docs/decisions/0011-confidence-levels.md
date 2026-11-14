# 0011: Every rated answer carries a confidence level, High, Medium or Low, computed by the backend from the check policy; High is exactly "certified"

- Status: accepted
- Date: 2026-11-14 17:10 (Europe/Helsinki)
- Decided by: Bogdan ("one fable agnet to research the onfidence levels and how to do that. The ocnfidence levels
  should be high medium low", 2026-11-14 16:2x; then, to the four choices put to him, "1. you reccomend 2. backend
  3. confidence.4 a": cut 0.20, the backend computes the level, the label is "Confidence", High at 98.9% is
  enough). Rule and field names: agent confidence (worker), accepted by Bogdan's orchestrator.
- Board thread: posted by the orchestrator (workers do not use the board)

## Context

- The three levels existed only in the frontend (`gradeOf`): High when `line.sure`, else Medium when the raw Gemini
  score was 0.8 or more, else Low. Measured on CubiCasa val (3,382 answers, check policy cross-fit): High 44.9% of
  answers at 98.9% exact, Medium 8.0% at 97.4%, Low 47.1% at 76.3%. Medium was as right as High, and Low mixed
  sink counts that are 89% right with window counts that are 55% right.
- The raw score is not a probability: answers scored 0.0 to 0.2 are 62.5% exact, and 0.8 or more is 99.0% exact.
- The check policy (`CHECK_POLICY`, `check_policy_v1`) already turns each family's signal into a calibrated
  P(wrong) and certifies below one cut. A second cut on the same number gives a middle level with a meaning.

## Decision

- **High** = the check policy certifies the answer (no double-check request). **Medium** = it asks, and the
  calibrated P(wrong) of its family's signal is at most 0.20. **Low** = every other rated answer. A level never
  contradicts the request: High never asks, Medium and Low always do.
- Other cases: a certified route (vector PDF, IFC model) is High; another route takes the level its own golden v2
  dev answers gave it (schedule tables: Medium, 37 of 39 on one sheet); a page flagged at upload, a value held for
  a check (two methods disagree, an estimate, edited and not signed off, a bedroom with no printed label) and
  anything not measured are Low, with the reason in `basis`.
- A value a person signed off or settled has no level (`level` null): it is theirs, and the screen shows the
  sign-off. A refusal has none. A policy file without levels gives none, instead of calling every answer Low.
- The policy file carries the levels, as optional fields of `check_policy_v1` written by
  `stoa_eval check-policy --medium 0.20`: `families.<family>.medium` (the lowest Medium score on the threshold's
  signal; null when the family's cross-fit Medium has under 30 answers or is under 80% exact),
  `routes.<route>.level` and `.dev` (`{units, exact}`), and `levels.crossfit.{high,medium,low}` (`{units, exact}`,
  the counts the sentences quote).
- API, additive: `level` on `POST /api/ask`'s answer, at the top level next to `confidence` and `check`, and
  `total_level` (the lowest part level) on the project ask. `line` (answer_v1.1, decision 0002) is unchanged.

```json
"level": {
  "level": "medium",
  "basis": "score",
  "text": "Medium confidence: on our validation plans, 91% of the answers rated this way were exact (1084 of 1185). Please double-check it."
}
```

- `basis` is one of `certified`, `route`, `score`, `page`, `held`, `unrated` (docs/API.md, "Confidence level").
- Code: `level_of` in `backend/app/core/review/check.py` (pure), the loader in `app/adapters/check_policy.py`.
  The frontend shows `level.level` under the label "Confidence" with `level.text`, and stops deriving a grade.

What the levels measured (share of answers, exact rate, Wilson 95% interval where given):

| | High | Medium | Low |
| --- | --- | --- | --- |
| CubiCasa val, cross-fit (3,382) | 44.9%, 98.9% [98.3, 99.3] | 35.0%, 91.5% [89.7, 92.9] | 20.1%, 58.4% [54.6, 62.0] |
| val, median of 50 halvings | 46.0%, 99.0% | 33.9%, 91.6% | 20.1%, 57.8% |
| golden v2 dev, raster (1,088) | 35.1%, 97.9% | 42.1%, 92.1% [89.3, 94.3] | 22.8%, 52.4% |
| CubiCasa test, the one read (3,359) | 37.9%, 99.0% [98.3, 99.4] | 41.1%, 92.8% [91.3, 94.0] | 21.0%, 54.2% [50.6, 57.9] |

The test row is the same single read of config C1-T1 as the check certificate, scored after the levels were
pre-registered on 2026-11-14 at 16:48:46 (the rule, and the thresholds by sha256); nothing was refit after it. It
is scored on the corrected certificate, where kitchens are answered from the drawing as the API does, with the
level the backend gives each answer. The first scoring, at 16:51 on the certificate's first run (kitchens from
the prior, all certified at one fixed score), gave High 41.8% at 98.2%, Medium 37.9% at 92.2% and Low 20.3% at
55.2%. Per family: [GOLDEN.md](../GOLDEN.md), "Confidence levels on test".

## Alternatives considered

- Keep the frontend rule (raw score 0.8): Medium is 8% of answers and as exact as High; Low holds 1,216 right
  answers (40.8% of them); families outside Gemini's 12 get no level.
- Medium when no second reader disputes the count: nothing fitted, but its Low is 68% exact (sinks 84%, toilets
  85%), and routes with one reader cannot have it.
- A cut of 0.10: Medium 94.1% on 22.7% of answers, Low 69.1% on 32.4% (val). Low then no longer means unreliable.
- A cut chosen so that Medium reaches 90%: it moves from 0.19 to 0.40 over 50 halvings.
- Levels in the frontend: every client would need the policy file's thresholds; one place computes it instead.

## Consequences

- `CHECK_POLICY` must point at a policy file generated with `--medium` for levels to show
  (`eval/results/check/check-C1-T1-recall96-rt-full-small-medium20.json` for config C1-T1); with a file that has
  no levels, `level` is null and nothing else changes.
- Known limits. High is "certified": 98.9% exact on val cross-fit and 99.0% on test,
  which is a measured rate, not a guarantee for one answer. Every window answer is Low: no
  runtime signal separates windows. The policy is fit on CubiCasa scans read with `ROOM_POLICY=gold-labels`.
  The vector and IFC High rests on 23 Swiss sheets and 11 models; a schedule's Medium on one sheet.
  A raster page with no plan and no located element found certifies nothing and its answers are Low (basis
  `page`): a safety rule added on 2026-11-14 (orchestrator, 17:24) after seeing 50 legacy archive sheets, not
  pre-registered, and after the test read. It costs 0 certified answers on CubiCasa val and golden v2 dev (no such
  page in either) and catches 1 of the 2 archive Sure-and-wrong toilet counts (61261280, read as blank); the
  blueprint case (1373, three bowls answered 2 with the detectors agreeing) stays open.
- Amendment, 2026-11-14 (brief r8 BQ; Bogdan 19:4x: "1. turn it on. 2. make them high I think", then "Make them
  High" after being told High would fall from about 99% exact): `CARBON_LEVELS=ladder`. Gemini Carbon reads each
  raster sheet beside the reader; a Medium answer it counts the same becomes High (basis `carbon`, "checked by
  Carbon: two readers agree"), one it counts differently becomes Low (as `demote`); refusing or failing changes
  nothing; it never certifies (`sure` stays false), and Low and High answers are left as they are. Measured at 0
  USD on the 256 val pages of integ's pre-registration 2 (.agents/exp/integ.md BQ; 2,271 units, Wilson 95%):

  | | High | Medium | Low |
  | --- | --- | --- | --- |
  | before (level B) | 44.9%, 99.0% [98.2, 99.5] | 35.5%, 92.4% [90.4, 94.1] | 19.6%, 58.4% [53.8, 62.9] |
  | ladder | 69.7%, 97.7% [96.8, 98.3] | 5.9%, 96.3% [91.6, 98.4] | 24.4%, 61.4% [57.3, 65.3] |

  The 563 Medium units Carbon agreed with are 95.2% exact [93.1, 96.7]: below the certified High, and below the
  135 Medium units it refused (96.3%). With ladder on, "High" no longer means certified, and the 99% figure
  holds only for basis `certified`. This was decided after the val numbers, not pre-registered, and is not
  measured on test.
- Revisit when the check policy changes (the levels are regenerated with it) or when a family gets a new signal.
