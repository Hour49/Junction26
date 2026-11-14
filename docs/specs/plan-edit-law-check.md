# Plan edits checked against the country's building rules (spec, backend + frontend)

Status: draft, 2026-11-14, by Tudor's law-kb orchestrator, for review by the agent-chat orchestrator (owner of
decision [0013](../decisions/0013-agent-chat.md) and [agent-chat.md](agent-chat.md)). Builds on: the box selection
of agent-chat AC-33 (unchanged), the plan proposals of AC-17/AC-18, the rule packs and check engine of decision
[0009](../decisions/0009-building-code-checks.md) (used as they are), and the law knowledge base of decision
[0014](../decisions/0014-law-knowledge-base.md).

Source, Tudor (2026-11-14): "can the user draw on the floor plan to signal to the ai what needs changing?" → "so we
should use the box maybe for this, write up a spec, is the ai telling you if your changes are illegal in that
country's laws?"

Requirement ids LC-n; tests name the id they cover.

## 0. The gap this closes

Today a person can drag a box on a plan (AC-33) and the agent proposes an edit (AC-17 remove a wall, AC-18 a new
room). The proposal carries plain-words flags (AC-19: structure, wet room, no door or window left) and the card says
"permits are not checked". The rule packs (0009) check the drawing **as read**, never a proposed change; the agent
*may* call `search_law`, but nothing makes it. So the answer to "is the AI telling me if my change breaks the law?"
is **no, not reliably**. This spec makes it yes for the rules we can check, and honest about the rest:

- Every proposal is checked in code, by the server, against the chosen country's rule pack, **before and after**
  the change; the person sees which rules the change would newly break, fix or leave unclear.
- The agent adds the clauses worth reading for this kind of change from the law knowledge base, as reading, not as
  a verdict.
- Words: never "legal" or "illegal". The pack's own sentence: "would not meet today's rule for a new building" (fi),
  "would not meet the Canton of Zürich's rule" (ch-zh). It is a pre-check of a few rules, not a permit check.

## 1. What the user can do (golden path)

Project: the swiss sheet `site980_bldg2055_floor9178.pdf` (as in agent-chat §1); country picker on **Canton of
Zürich** (`?pack=ch-zh`).

1. Press "Point at the plan", drag a box over part of Stanza 1.02 (16.48 m²), ask "Put a storage room here".
2. The edit card shows the new room and Stanza 1.02 shrinking to e.g. 8.9 m², and a section **Building rules ·
   Canton of Zürich** with one row: ✕ **Would not meet** · "A bedroom or living room is at least 10 m2 (canton of
   Zürich)" · Stanza 1.02: 16.48 → 8.9 m², at least 10 m² · PBG § 303 Abs. 1 (link, quote on open). Under it:
   "Other rules to read" with up to 3 clauses the agent found (e.g. PBG § 302 on daylight), each with ref and link.
3. The agent's text says it in one sentence: "Stanza 1.02 would be 8.9 m²; Zürich's rule asks at least 10 m² for a
   bedroom or living room (PBG § 303 Abs. 1) [2]."
4. Same box, country picker on **Finland**: the row reads ✓ **Meets** (limit 7 m², 631/2024 4 § 2 mom.).
5. No country picked: the section reads "Pick a country to check this change against its building rules" with a
   link that opens the picker; nothing is said about law.
6. Remove the wall between Bagno 1.01 and Stanza 1.02 (agent-chat §1 step 2): the section lists the rules the merged
   room still meets and any window rule that turns unclear, never a "pass" for structure ("not checked" note stays).

## 2. Backend

### 2.1 The check (pure, `app/core/plan_edit/law_check.py`; imports `app.core.checks.check`, no adapter)

- LC-1 `check_proposal(drawing, proposal, pack, route) -> LawCheck`: builds the **after** drawing from a copy of
  `drawing` (only the proposal's page changes): rooms in `proposal.rooms` replaced by their after-geometry
  (`polygon`, `area_m2 = area_after_m2`, `area_status` as the proposal's area source; a new room from AC-18 added),
  rooms listed in `was` removed, walls/doors in `removed` dropped, `added` walls and doors kept as elements. Then
  `check_drawing(before, pack, route)` and `check_drawing(after, pack, route)` (0009's engine, unchanged).
- LC-2 Room types after the change: a shrunk room keeps its type; a merged room is checked **as each type it came
  from** (a bedroom merged into a bathroom still meets or fails the bedroom rules); a new room's type comes from its
  name with the same room-word table the reader uses (`storage` for "storage", "Abstellraum", "varasto"), else
  `other` (then 0009's "rooms of a kind we could not tell" makes room rules cannot tell, with that reason).
- LC-3 `LawCheck = {pack, pack_name, fail_means, findings: [Finding], unchanged: int, note}`. A `Finding` is one
  (rule, room/door) result whose status differs before → after, or that fails after and touches the proposal
  (a room in `rooms` or `was`, a door in `removed`/`added`, a room the new room overlaps):
  `{rule_id, title, change: "newly_fails" | "now_passes" | "newly_cannot_tell" | "still_fails", subject (room or door
  label), before: {status, value}, after: {status, value, why}, comparison_text, limit, unit, clause: {ref, url,
  quote, quote_en}}`. Ordered: newly_fails, still_fails, newly_cannot_tell, now_passes. `unchanged` = how many
  checked results did not change (shown as "N other checks unchanged").
- LC-4 Never a stronger verdict than 0009 allows: if the after value rests on an estimate or a picture route, the
  engine's cannot tell stands; an after-area computed by geometry from **drawn** polygons on a vector sheet is as sure
  as the before-area it came from (`sure` copied, never raised).
- LC-5 `note` = "A pre-check of {n} rules from {pack_name}, not a permit check. Structure, fire safety, escape routes
  and services are not checked." (n = the pack's rule count).

### 2.2 Wiring into the agent (0013 contract deltas)

- LC-6 Request: `POST /api/projects/{id}/chat` body gains `pack?: "fi" | "ch-zh" | null` (the header's country
  picker, the same `?pack=` the checks screen sends; not stored on the project, as in 0009). Unknown pack → 422.
  The chat keeps the pack per turn (a turn can switch it).
- LC-7 The plan tools (`propose_remove_wall`, `propose_room`) run `check_proposal` right after building the proposal
  when a pack is set, and put `law` on it: `edit.law = LawCheck | null` (null: no pack). Computed by the server; the
  model cannot skip or change it. The tool result the model reads includes `law.findings` with an ev id per finding
  (AC-5 walks `page`/`box` of the subject's mark).
- LC-8 Validator (0013 rule 3 extended): an `edit` turn whose `law.findings` has a `newly_fails` must cite at least one
  of those findings' ev ids in its text; else one retry, then the server appends "This change would not meet {n}
  rule(s) of {pack_name}: see Building rules." The text never says "legal", "illegal", "allowed" or "compliant"
  (validator: those words → retry, then removed sentence).
- LC-9 Related clauses: with a pack set, after a plan tool the agent calls `search_law(pack, query)` at least once
  with the change in words (e.g. "remove wall bathroom", "new storage room bedroom area"); `edit.related_law` =
  up to 3 `{clause_id, ref, title_en, summary_en, url}` it chose, each from a `search_law`/`get_clause` result of
  this turn (validator: ids must come from this turn). Shown as reading; no status. `RulesChatModel` (no-keys mode)
  calls `search_law` with the proposal's room types and takes the top 3.
- LC-10 Proposal accept/reject (0013) is unchanged: a person may accept a proposal that would not meet a rule;
  the accepted proposal keeps its `law` as it was computed.

### 2.3 API example (the `edit` object of 0013, new fields only)

```json
"law": {
  "pack": "ch-zh", "pack_name": "Canton of Zürich building act",
  "fail_means": "It would not meet the Canton of Zürich's rule; other cantons set their own.",
  "findings": [{
    "ev": "ev_2", "rule_id": "ch-zh-room-area",
    "title": "A bedroom or living room is at least 10 m2 (canton of Zürich)",
    "change": "newly_fails", "subject": "Stanza 1.02",
    "before": {"status": "pass", "value": 16.48}, "after": {"status": "fail", "value": 8.9, "why": null},
    "comparison_text": "at least", "limit": 10, "unit": "m2",
    "clause": {"ref": "Planungs- und Baugesetz des Kantons Zürich (PBG, LS 700.1), § 303 Abs. 1",
               "url": "https://…", "quote": "…", "quote_en": "…"}
  }],
  "unchanged": 6,
  "note": "A pre-check of 2 rules from Canton of Zürich building act, not a permit check. Structure, fire safety, escape routes and services are not checked."
},
"related_law": [{"clause_id": "ch-zh-ls-700-1-302-1", "ref": "§ 302 Abs. 1", "title_en": "Planning and Building Act", "summary_en": "…", "url": "https://…"}]
```

## 3. Frontend (`frontend/src/agent/`, the edit card of agent-chat AC-32)

- LC-11 The chat sends the route's pack with every turn (`chatTurn(projectId, {…, pack})`).
- LC-12 Edit card section **Building rules · {country_name}** under the change list: one row per finding: a status
  word with an icon (✕ Would not meet · ! Can't tell · ✓ Meets now · ✕ Still doesn't meet; colour never alone), the
  rule title, `subject: before → after` against "{comparison_text} {limit} {unit}", the clause ref as a link
  (new tab), the quote behind a disclosure with "Translation ours, unofficial" under `quote_en`. "N other checks
  unchanged" as a quiet line. The `note` last. Rows with `newly_fails` first and open by default.
- LC-13 "Other rules to read": `related_law` as up to 3 links (ref · title · summary), no status icon.
- LC-14 No pack: the section shows the pick-a-country line and a button that opens the header's country picker.
- LC-15 A finding row's subject is clickable: it highlights the room on the edit card's plan (its ev mark).
- LC-16 Phone width 390: rows stack (status + title, then values, then clause); no horizontal scroll.

## 4. Tests

- Core (synthetic rectangles, no data): a 12 m² bedroom, a storage box taking 3 m² → ch-zh room-area newly_fails
  (9 < 10), fi meets (≥ 7); the same box on a 20 m² bedroom → no finding, `unchanged` counts it; a merged
  bathroom+bedroom checked as both types; a new room named "Schlafzimmer" with no window → room-window newly_fails or
  cannot tell per 0009's balcony-door rule; an estimated area → cannot tell, never fail; no pack → `law` null.
- On floor9178 when `data/stoa/full` is present (skip otherwise): golden path §1 steps 1-4 values.
- Loop: scripted model whose edit text skips the failing rule → retry → appended sentence (LC-8); text with
  "illegal" → retry; `related_law` id not from this turn → rejected.
- API (`CHAT_MODEL=rules`): edit turn with `pack=ch-zh` carries `law` + `related_law`; `pack` unknown → 422; no pack
  → `law` null.
- Frontend: card fixtures for each `change` kind and for no pack; e2e on the no-keys backend: box → storage room →
  "Would not meet" row visible; screenshots 1440 and 390.

## 5. Out of scope tonight

Pass/fail on law outside the rule packs (it stays reading via `related_law`); fire distances, escape routes,
structure and services; adding rules to the packs (codecheck's, 0009); permit procedure advice; checking a change
against a municipal zoning plan (BZO / asemakaava).

## 6. Owners (proposed)

- Agent-chat fleet (w5:p1): LC-6 to LC-10, LC-11 to LC-16 (its files: `app/core/agent/`, `plan_tools.py`,
  `src/agent/`).
- Law-kb fleet: LC-1 to LC-5 (`app/core/plan_edit/law_check.py` + tests), against the proposal model as merged.
- No change to `app/core/checks/` or `backend/app/rules/` (Bogdan's codecheck); if one is needed it goes to #220.
