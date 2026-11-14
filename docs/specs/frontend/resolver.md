# Resolver: Carbon's picks on conflicts, issues and answers (spec, #252)

Status: draft for review, 2026-11-14 19:05, by fe-shared (phase 1: spec + fixtures). Phase 2 (builds) starts after
the carbon-flag PR merges. Brief: `.agents/briefs/fe-resolver.md` (Bogdan #14 c6880353751 + c6880670542).
Contract: `docs/API.md` "`POST /api/projects/{project_id}/resolve`" (backend on main, `RESOLVER=off|carbon`,
default off).

## Purpose

With `RESOLVER=carbon`, a model looks at each conflict no rule decides and nobody settled, and either picks one of
the methods' values or says it can't tell. The UI says plainly that the value was picked by a model, why, and that
the person can change it. Nothing reads as certain because of a pick.

## Data (all fields absent while `RESOLVER` is off: every screen then looks as before)

- `Resolved` (`src/api/types.ts`, = `Schemas['Resolved']`): `{verdict: 'picked' | 'cannot_tell', value: number |
  null, reason: string (one sentence), marks: ValueMark[] (1-based page, page-fraction box, same frame as
  value_marks), by: 'carbon:<model>', at, of: number[]}`. On `ConflictEntry`, takeoff `Row`, `Issue`, `AnswerView`,
  and in every settle/unsettle/reset/sign-off response. The brief's `cost_usd` is not on it (the schema has none;
  an answer's `cost_usd` includes the call).
- `ProjectSummary.conflicts_picked` / `ProjectView.conflicts_picked` (int, absent or null = 0): picks in use. A
  pick in use is NOT in `conflicts_open`; a `cannot_tell` stays in `conflicts_open` and `needs_person`.
- A pick in use: `resolved.verdict === 'picked'`, `needs_person` false, no `settled`, no `signed`; the row's
  `value` is the pick, `conflict.status` stays `conflict`. A person's settle, sign-off or mark edit wins
  (`needs_person` true again after a mark edit); unsettle/reset bring the pick back.
- `Issue` of a picked conflict: still listed, `state: open`, severity `note`, `resolved` set: not counted in
  `issues_to_answer` nor by `needsYou` (it excludes `note`). `cannot_tell` stays `needs_person`.
- `AnswerView.resolved`: beside an uncertain answer (`check` set). `AnswerView.resolver_note: string | null`: the
  model's value matched no method (no `resolved`).
- `POST /api/projects/{id}/resolve` → `Resolving {review, notes}`: no UI in this round (it runs by itself after
  ingest); no client function until a screen needs it.

Fixtures (`src/api/fixtures.ts`, from `backend/tests/fixtures/api_v1`): `projectResolved` (conflicts_picked 1,
conflicts_open 0, issues_to_answer 0), `projectReviewResolved` (conflict 0 picked 22.401 of [22.401, 30.0]),
`resolving` (conflict 0 `cannot_tell`, value null, needs_person true; notes []), `answerResolved` (doors, level
medium, check set, picked 2). No Issue fixture carries `resolved`: issue tests spread `projectIssues.issues[0]` with
`severity: 'note'` and `resolved: projectReviewResolved.conflicts[0].resolved`.

## Words

- Who: "Picked by Carbon" — the name is `by`'s prefix before `:`, capitalised; the model id (after `:`) only in a
  `title` tooltip ("carbon:gemini-4-carbon"). Never "AI", never the model id in visible text.
- Why: `resolved.reason` verbatim, one sentence.
- Then "You can change it" next to the existing Modify/settle control (no new control).
- `cannot_tell`: "Carbon could not tell" + the reason; the conflict stays open (Needs you).
- List line: "N picked by Carbon, check them."
- The server's `why` names the model id ("A model (carbon:gemini-4-carbon) checked..."): where a card shows `why`
  and `resolved` is set, it shows `why` only up to and including "No rule decides between them." and the lines above
  instead.

## Shared helpers (fe-shared, `src/api/format.ts`)

- `resolverName(by: string): string` → `'carbon:gemini-4-carbon'` → `Carbon`; no colon → the whole string
  capitalised.
- `resolverModel(by: string): string` → the part after the first `:` (whole string when none).
- `pickInUse(r: {resolved?: Resolved | null; needs_person: boolean; settled?: unknown; signed?: unknown}): boolean`
  → the "pick in use" rule above. Works on `ConflictEntry` and `Row`.

## Acceptance criteria

Each is a unit/component test against the fixtures above (mockApi for screens). Owner in brackets.

fe-shared (counts, badge, helpers, fixtures):
- RS-1 (fixtures, done in phase 1) `projectResolved`: conflicts_picked 1, conflicts_open 0, issues_to_answer 0.
- RS-2 (fixtures, done) `projectReviewResolved.conflicts[0]`: status conflict, needs_person false, settled null,
  verdict picked, value = resolved.value, by starts `carbon:`, reason and marks non-empty.
- RS-3 (fixtures, done) `resolving.review.conflicts[0]`: cannot_tell, value null, needs_person true; notes [].
- RS-4 (fixtures, done) `answerResolved`: picked, check set, level not high.
- RS-5 `resolverName('carbon:gemini-4-carbon')` → `Carbon`, `resolverModel(...)` → `gemini-4-carbon`;
  `resolverName('carbon')` → `Carbon`.
- RS-6 `pickInUse(projectReviewResolved.conflicts[0])` true; false with `settled` set, with `needs_person` true,
  with `resolved` absent, and for `resolving.review.conflicts[0]`.
- RS-7 Header badge with a picked issue (severity note, resolved set) and `issues_to_answer` 0: no badge; under
  `?pack` (SH-88) `needsYou` also skips it.
- RS-8 Workspaces list (`src/account`): a project with `conflicts_picked: 2` shows a neutral pill "2 picked by
  Carbon" (1 → "1 picked by Carbon"); absent, null or 0 → no pill; `to_review` pill unchanged.

fe-surveyor (conflict card + list count, `src/surveyor`):
- RS-10 `cardState` gets a fourth state `picked` for `pickInUse(c)` (before `rule`): the card for
  `projectReviewResolved.conflicts[0]` shows "Picked by Carbon" (tooltip `gemini-4-carbon`), the reason verbatim,
  "You can change it" beside the existing Modify/settle control, and the tile at the pick (22.40 m²) is the one in
  use. It never says "settled by a rule" and never "AI".
- RS-11 The pick's `resolved.marks` are drawn on the card's plan in the same frame as `value_marks`, with their
  labels.
- RS-12 `resolving.review.conflicts[0]` (cannot_tell): state open ("Needs you"), plus "Carbon could not tell" and the
  reason; no tile in use.
- RS-13 `subLine` counts picks apart: one picked conflict → "1 picked by Carbon, check them." (other parts as
  before); `progressText` counts a pick as settled (needs_person false).
- RS-14 Settling a picked card posts the existing settle; the response with `settled` set shows "settled by you";
  an unsettle response bringing `resolved` back shows the pick again.
- RS-15 Neither card nor table shows the model id from `why` (rendered `why` stops after "No rule decides between
  them."). The takeoff table row with a pick in use reads "Picked by Carbon" in its status cell.

fe-engineer (answer card + chat, `src/engineer` (ProjectChat lives there)):
- RS-20 `answerResolved`: the answer's value (2), level word (medium) and check line are unchanged; beside them
  "Picked by Carbon: 2" with the reason; never the sure/high wording, no certified badge.
- RS-21 `answerResolved` with `resolved.verdict: 'cannot_tell'`, value null: "Carbon could not tell" + reason.
- RS-22 `resolver_note: "<text>"` and no `resolved`: the note shown as a muted line under the check; null → nothing.
- RS-23 Chat's answer card (CH-*) shows the same lines as RS-20..22.

fe-ingest (Documents issue rows + ingest gate, `src/documents`, `src/ingest`):
- RS-30 An issue with `resolved` (picked, severity note): the row shows "Picked by Carbon" (the model id as its
  `title`, `resolverName`/`resolverModel`), the reason and a link "You can change it" → the conflict card
  (`issueRoute`, fe-surveyor); pill "Note"; not in `needsYou`. Only conflict issues carry `resolved` (backend
  `app/api/issues.py`) and Documents leaves conflicts out (DOC-3), so a conflict issue WITH `resolved` is listed
  on Documents (fe-ingest, 2026-11-14): Carbon's picks need a person's look; conflicts without it stay on Ingest.
- RS-31 An issue with `resolved.verdict: 'cannot_tell'` (needs_person): pill as before ("Needs a person") plus
  "Carbon could not tell", the reason and a link "Settle the conflict" → the conflict card; counted by `needsYou`
  (as the server's `issues_to_answer`, which counts every open non-note issue). No answer form on either: a conflict
  is settled on its card.
- RS-32 IngestFinished with `projectResolved` + `projectReviewResolved`: "Start a new chat" is not locked (the pick
  needs nobody); with `resolving.review` it stays locked.

## Open points

1. `Resolved.cost_usd` is in the brief, not the schema: nothing shows a resolver cost this round.
2. The picks' marks on the Documents plan (RS-30) are optional: the issue's own `box` already points at the place.
