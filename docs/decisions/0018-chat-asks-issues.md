# 0018: Before it answers, the chat asks about an open issue the answer rests on

- Status: accepted
- Date: 2026-11-15 (Europe/Helsinki)
- Decided by: Madalina (2026-11-15: the feature, and decisions D1-D6 below), through her orchestrator; built by
  worker issue-ask. Design: `.agents/research/issue-ask-design.md` (local).

## Context

A question about a drawing can rest on an issue nobody answered: a conflict no rule decides, a reading with a
caveat, a refusal. The chat answered over it, and the issue waited in a list. The Documents tab's "Issues on
demand" list is gone; the issue is now asked where the question is.

## Decision

- **When** (server-side, never a model's guess): after `ask_drawings` answers in a chat turn, the project's issues
  (`GET …/issues` without a pack) are matched to the answer (`app/core/agent/issue_ask.py` `related`). An issue is
  asked when it is `open`, has no `answer`, was not skipped, and is one of (D1): a `needs_person` `conflict` on the
  same drawing and quantity key (a storey's row is its sheet's); a `reading_flag` on a drawing that gave a value; an `unrelated_file` the judge was unsure about, when every
  drawing refused. Refusals and set-aside files (notes) and code checks are not asked.
- **The ask**: the turn ends there with `kind: "ask_issue"`, `issue` (the issue as the list gives it: label, why,
  place, suggestions) and `options`: a conflict's method values (`value` set: picking one settles it), the issue's
  `suggestions`, then "Skip for now" (`skip: true`). The model writes no answer in that turn; the `ask_drawings`
  result stays in the chat. The question is held on the chat (`pending`).
- **The answer**: the next `POST …/chat` (or `/chat/stream`) carries `issue_answer: {issue_id, text, by, value?,
  skip}` with `message` (what the person sees as theirs). 422 when the chat is not asking about that issue. A
  `value` on a conflict is a person's `settle` of the quantity (D3, the note names the person); every answer but a
  skip is kept as the issue's `answer` (`POST …/issues/{id}/answer`'s store), so the issue is answered everywhere.
- **Then the real answer**: the same request runs a normal turn on the held question, with a line telling the model
  what the person said (D5: issues already answered are not asked; their answers go to the model with the
  `ask_drawings` result as `people_answered`).
- **Skip** (D2): nothing is saved on the issue; the skip is kept with the project (`<projects dir>/api/issue_skips/
  <project id>.json`), so that issue is never asked again, in this chat or a new one. The answer ends, in the
  server's words, "This rests on an open issue on <drawing>: <label>. Do you have other questions?" and the chat
  goes on.
- At most 2 asks per question (D1). The rules planner (no keys) gets the same flow (D6): the ask is the server's.
- The issue card moved from Documents to `frontend/src/issues/IssueCard.tsx` (D4); the chat shows the asked issue
  with it, the choices in place of its answer form.

## Consequences

- Additive to API v1: `ChatTurn.kind` gains `ask_issue`, `ChatTurn.issue`, `Option.value` and `Option.skip`,
  `ChatRequest.issue_answer`.
- A turn that asks costs one `ask_drawings` call and no model answer; the answer turn asks the drawings again (the
  settled value is then the drawing's).
- When the issues can't be listed, the turn answers without asking (logged).
