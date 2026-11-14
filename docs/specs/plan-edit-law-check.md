# Plan edits checked against the country's building rules (spec, backend + frontend)

Status: reviewed (agent-chat orchestrator, review in its `.agents/agent-chat/law-spec-review.md`: OK with 5 fixes
and 4 changes, all taken), 2026-11-14, by Tudor's law-kb orchestrator. Base: branch `agent/chat` (PR #261), whose
`app/core/plan_edit/` model (Proposal, RoomChange, Item) this builds on. Owner of
decision [0013](../decisions/0013-agent-chat.md) and [agent-chat.md](agent-chat.md)). Builds on: the box selection
of agent-chat AC-33 (unchanged), the plan proposals of AC-17/AC-18, the rule packs and check engine of decision
[0009](../decisions/0009-building-code-checks.md) (used as they are), and the law knowledge base of decision
[0014](../decisions/0014-law-knowledge-base.md).

Source, Tudor (2026-11-14): "can the user draw on the floor plan to signal to the ai what needs changing?" → "so we
should use the box maybe for this, write up a spec, is the ai telling you if your changes are illegal in that
country's laws?" → "make the ai for a modification look up in the law db with that tooling so it can tell you
exactly what law/rule you re breaking".

Requirement ids LC-n; tests name the id they cover.

## 0. The gap this closes

Today a person can drag a box on a plan (AC-33) and the agent proposes an edit (AC-17 remove a wall, AC-18 a new
room). The proposal carries plain-words flags (AC-19: structure, wet room, no door or window left) and the card says
"permits are not checked". The rule packs (0009) check the drawing **as read**, never a proposed change; the agent
*may* call `search_law`, but nothing makes it. So the answer to "is the AI telling me if my change breaks the law?"
is **no, not reliably**. This spec makes it yes for the rules we can check, and honest about the rest:

- Every proposal is checked in code, by the server, against the chosen country's rule pack, **before and after**
  the change; the person sees which rules the change would newly break, fix or leave unclear.
- For the rest of the law (most of it has no rule-pack check), the agent looks the change up in the law knowledge
  base (0014) every time and names the exact clause it believes the change would not meet, quoting its number and
  ref; the server checks that claim against the clause's own `limits` and the proposal's numbers before it is shown,
  and the card labels it as the AI's reading, apart from the code's rule checks.
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

- LC-1 `check_proposal` (signature in §2.4) builds the **after** drawing from a copy of `drawing`; only
  `proposal.page` changes:
  - Each `RoomChange` replaces its rooms: a merge (`id "R1+R2"`, `was ("R1", "R2")`) removes the `was` rooms and adds
    one room; a shrunk room (same `id` as a drawing room, no `was`) replaces that room; a new room (an id not in the
    drawing, no `was`) is added. `was` is per RoomChange, never on the proposal.
  - Polygons: `RoomChange.polygon` / `Item.polygon` are page-fraction rings (0..1, top left); they are converted to
    the page's own units with `drawing.pages[page].width/height` before they go into the after `Room.polygon`/`box`.
  - Removed `Item`s: only doors carry a drawing element id (`e6`) and are dropped from the after elements. Wall items
    on Swiss sheets are fill strips (`W1`, `W1.2`, ids from `walls_of`), not drawing elements: nothing to drop.
  - Then `check_drawing(before, pack, route)` and `check_drawing(after, pack, route)` (0009's engine, unchanged).
- LC-2 Room types after the change: a shrunk room keeps its type; a merged room is checked **as each type it came
  from** (a bedroom merged into a bathroom still meets or fails the bedroom rules); a new room's type comes from its
  name with the same room-word table the reader uses (`storage` for "storage", "Abstellraum", "varasto"), else
  `other` (then 0009's "rooms of a kind we could not tell" makes room rules cannot tell, with that reason).
- LC-3 `LawCheck = {pack, pack_name, fail_means, findings: [Finding], unchanged: int, related, ai_findings,
  subjects, subject_values, note}`. A `Finding` is one (rule, room/door) result whose status differs before →
  after, or that fails or passes after and touches the proposal (a room in `rooms` or `was`, a door in
  `removed`/`added`, a room the new room overlaps):
  `{ev, rule_id, title, change: "newly_fails" | "now_passes" | "newly_cannot_tell" | "still_fails" |
  "still_passes", subject (room or door label), subject_ref (its room, RoomChange or door id), before: {status,
  value}, after: {status, value, why}, comparison_text, limit, unit, clause: {ref, url, quote, quote_en}}`.
  `still_passes`: pass → pass on a touched subject (§1 step 4, Finland "✓ Meets"). A new room has no before:
  `before = {status: "not_applicable", value: null}`. `ev` is null from `check_proposal`; the agent loop sets it.
  Ordered: newly_fails, still_fails, newly_cannot_tell, now_passes, still_passes. `unchanged` = how many checked
  results did not change on what the proposal does not touch (shown as "N other checks unchanged").
  `subjects`: the labels and ids of the rooms and doors the proposal changes. `subject_values`: per changed room
  and new door, by id and by label, its numbers: a room's after area on the drawing's basis (LC-4) and as the
  geometry measures it, a new door's width from its outline at the drawing's scale (LC-9b ties a note's value to
  them).
- LC-4 After areas (one rule, so printed-before and geometry-after never make a false change): RoomChange areas
  are geometry on both sides, the drawing's `Room.area_m2` is often printed (Stanza 1.02: 16.48). So:
  - shrunk room: `area_m2 = before.area_m2 × area_after_m2 / area_before_m2`;
  - merge: `area_m2 = Σ was.area_m2 × area_after_m2 / area_before_m2`;
  - new room: `area_m2 = area_after_m2`;
  - `area_source = "geometry_x_scale"`; `area_status` and `area_uncertainty` copied from the source room (the weakest
    of the `was` rooms: `estimated` if any is); a new room takes the page's: `None` on a vector/CAD/BIM route at a
    real scale, else `estimated` with no stated error.
  This stays inside 0009's own rule: a fail stands on a printed area or a drawn vector outline at a real scale; an
  estimate or a picture stays cannot tell. A proposal on a scan can therefore say "can't tell", never "would not
  meet". No verdict is ever stronger than the engine gives.
- LC-5 `note` = "A pre-check of {n} rules from {pack_name}, not a permit check. Structure, fire safety, escape routes
  and services are not checked." (n = the pack's rule count).

### 2.2 Wiring into the agent (0013 contract deltas)

- LC-6 Request: `POST /api/projects/{id}/chat` body gains `pack?: "fi" | "ch-zh" | null` (the header's country
  picker, the same `?pack=` the checks screen sends; not stored on the project, as in 0009). An unknown pack → 422
  through the same known-pack lookup the checks API uses (`app/api/checks.py` `pack_of`), not a second list. A turn
  can switch the pack.
- LC-7 The plan tools (`propose_remove_wall`, `propose_room`) run `check_proposal` right after building the proposal
  when a pack is set, and put `law` on it: `edit.law = LawCheck | null` (null: no pack). Computed by the server; the
  model cannot skip or change it. The tool result the model reads carries `LawCheck.for_model()`: each finding
  without `clause.quote`/`quote_en` (title, subject, before/after, limit, unit, clause ref, ev id), so it stays well
  under TOOL_CHARS; the full clause goes only on the ChatTurn for the card.
- LC-8 Validator (0013 rule 3 extended): an `edit` turn whose `law.findings` has a `newly_fails` must cite at least one
  of those findings' ev ids in its text; else one retry, then the server appends "This change would not meet {n}
  rule(s) of {pack_name}: see Building rules." The text never says "legal", "illegal", "compliant" or "permitted"
  (not "allowed": it shows up innocently); on those words: one retry, then the sentence is removed. An edit turn is
  never turned into dont_know for wording.
- LC-9 Law lookup, run in code for every proposal (cannot be skipped): the plan tool runs
  `index.search(pack, related_query(drawing, proposal), limit=8)` (law index of 0014; `related_query` is ours, LC-1's
  module: the changed rooms' types and the change in words, in English and the pack's language, e.g. "bedroom room
  area minimum Schlafzimmer Fläche" or "remove wall bathroom wet room") fetches each hit with `index.clause(id)` and passes those
  ClauseViews to `check_proposal(..., related=...)`. `law.related` = them, ordered checkable-with-limits first. `for_model()` includes them (ref, title, summary, limits;
  no quotes).
- LC-9a The agent judges them: for each related clause with `limits` that applies to a changed room or door (the
  model reads the summary and decides whether e.g. "habitable room area" fits "Schlafzimmer"), it may call
  `get_clause` and then lists it in `final_answer(..., law_notes=[...])`:
  `{clause_id, subject, value, comparison, limit, unit, verdict: "would_not_meet" | "meets" | "check"}`
  (`check`: applies, but the drawing lacks the value, e.g. a window's light area).
- LC-9b The server validates every `law_note` before it is kept (rules of 0013 §3 plus): `clause_id` came from this
  turn's `law.related`, `search_law` or `get_clause`; `limit`, `comparison` and `unit` equal one entry of that clause's
  `limits`; `subject` is a room or door the proposal changes (`law.subjects`); `value` equals one of **that
  subject's own** numbers (`law.subject_values` of the most specific id or label the subject names, after a
  mm/cm limit is put back in metres), so another room's area, though a tool gave it this turn, never stands for
  it; no value only with verdict `check`; `verdict` agrees with `value comparison limit` (computed
  again in code, never taken from the model), and `check` whatever the model said when the limit's `what` is on a
  whole (any dwelling/apartment/flat/unit/building/storey/house word or total, FI/DE/FR too, unless it only says
  where the element is, e.g. "in one-room dwellings": lawai-2), since the subject is one room or door. A failing note is dropped and the turn gets one retry; a note that
  repeats a rule-pack finding (same clause ref) is dropped as duplicate. Kept notes → `law.ai_findings`, each with
  the full clause (`ref`, `url`, `quote`, `quote_en`, law title) filled in by the server.
- LC-9c The text: a kept `would_not_meet` note must be named in the answer with its ref ("PBG § 303 Abs. 1 asks at
  least 10 m²; Stanza 1.02 would be 8.9 m²"), else the LC-8 append sentence covers it too. The `RulesChatModel` (no
  keys) adds no `law_notes`: only rule-pack findings and `law.related` reach the card.
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
    "change": "newly_fails", "subject": "Stanza 1.02", "subject_ref": "r2",
    "before": {"status": "pass", "value": 16.48}, "after": {"status": "fail", "value": 8.9, "why": null},
    "comparison_text": "at least", "limit": 10, "unit": "m2",
    "clause": {"ref": "Planungs- und Baugesetz des Kantons Zürich (PBG, LS 700.1), § 303 Abs. 1",
               "url": "https://…", "quote": "…", "quote_en": "…"}
  }],
  "unchanged": 6,
  "ai_findings": [{"clause_id": "fi-241-2017-4-2", "subject": "new door D1", "value": 700, "comparison": ">=", "limit": 800,
                   "unit": "mm", "verdict": "would_not_meet", "ref": "4 § 2 mom.",
                   "law": "Government Decree on the accessibility of buildings",
                   "url": "https://…", "quote": "…", "quote_en": "…", "basis": "ai_reading"}],
  "related": [{"id": "ch-zh-ls-700-1-302-2", "law_id": "ch-zh-ls-700-1", "ref": "§ 302 Abs. 2", "law_title_en": "Planning and Building Act of the Canton of Zürich", "summary_en": "…", "url": "https://…", "limits": [{"what": "window area …", "comparison": ">=", "value": 10, "unit": "%"}], "drawing_checkable": true, "…": "the rest of the ClauseView (§2.4)"}],
  "subjects": ["Ripostiglio", "N1", "Stanza 1.02", "r2"],
  "subject_values": {"N1": [6.56], "Ripostiglio": [6.56], "r2": [9.5], "Stanza 1.02": [9.5]},
  "note": "A pre-check of 2 rules from Canton of Zürich building act, not a permit check. Structure, fire safety, escape routes and services are not checked."
}
```

## 3. Frontend (`frontend/src/agent/`, the edit card of agent-chat AC-32)

- LC-11 The chat sends the route's pack with every turn (`chatTurn(projectId, {…, pack})`).
- LC-12 Edit card section **Building rules · {country_name}** under the change list: one row per finding: a status
  word with an icon (✕ Would not meet · ! Can't tell · ✓ Meets now · ✕ Still doesn't meet · ✓ Meets for
  `still_passes`; colour never alone), the
  rule title, `subject: before → after` against "{comparison_text} {limit} {unit}", the clause ref as a link
  (new tab), the quote behind a disclosure with "Translation ours, unofficial" under `quote_en`. "N other checks
  unchanged" as a quiet line. The `note` last. Rows with `newly_fails` first and open by default.
- LC-13 Two more blocks under the rule-pack rows: **"The AI also found in the law"**: `law.ai_findings`, one row each
  with the same status words as LC-12, the clause ref + law title as a link, the quote behind a disclosure, and the
  label "AI reading of the law, checked against the clause's number; not a rule check"; then **"Other rules to
  read"**: up to 3 of `law.related` not already shown, as links (ref · title · summary), no status.
- LC-14 No pack: the section shows the pick-a-country line and a button that opens the header's country picker.
- LC-15 A finding row's subject is clickable: it highlights the room on the edit card's plan (its ev mark).
- LC-16 Phone width 390: rows stack (status + title, then values, then clause); no horizontal scroll.

## 4. Tests

- Core (synthetic rectangles, no data): a 12 m² bedroom, a storage box taking 3 m² → ch-zh room-area newly_fails
  (9 < 10), fi meets (≥ 7); the same box on a 20 m² bedroom → no finding, `unchanged` counts it; a merged
  bathroom+bedroom checked as both types; a new room named "Schlafzimmer" with no window → room-window newly_fails or
  cannot tell per 0009's balcony-door rule; an estimated area → cannot tell, never fail; no pack → `law` null.
- On floor9178 when `data/stoa/full` is present (skip otherwise): golden path §1 steps 1-4 values.
- Core LC-4: printed 16.48 m² room shrunk by geometry 16.40 → 8.88 → after 8.92 (printed basis), fails ch-zh; the
  same on an estimated room → cannot tell; Swiss wall strips in `removed` leave the elements unchanged; a door item
  drops its element.
- Loop LC-9b: a scripted model's `law_note` with a limit not in the clause, a clause not from this turn, a value no
  tool returned, or a verdict that contradicts its numbers → dropped + retry; a correct note → `ai_findings` with the
  server-filled quote.
- Loop: scripted model whose edit text skips the failing rule → retry → appended sentence (LC-8); text with
  "illegal" → retry, then removed.
- API (`CHAT_MODEL=rules`): edit turn with `pack=ch-zh` carries `law` with `related`; `pack` unknown → 422; no pack
  → `law` null.
- Frontend: card fixtures for each `change` kind and for no pack; e2e on the no-keys backend: box → storage room →
  "Would not meet" row visible; screenshots 1440 and 390.

## 5. Out of scope tonight

A code-made pass/fail on law outside the rule packs (that is the AI's reading, LC-9a/b, labelled as such); fire distances, escape routes,
structure and services; adding rules to the packs (codecheck's, 0009); permit procedure advice; checking a change
against a municipal zoning plan (BZO / asemakaava).

### 2.4 Interface (final, posted on board #241)

```python
# app/core/plan_edit/law_check.py (pure core; imports app.core.checks, app.core.laws.model, plan_edit.model)
def check_proposal(
    drawing: Drawing,            # the proposal's drawing as read (before)
    proposal: Proposal,          # app/core/plan_edit/model.py on agent/chat
    pack: RulePack,              # from checks' pack_of
    route: Route | None,         # DrawingInfo.route; None = taken as a picture (0009)
    related: Sequence[ClauseView] = (),  # [index.clause(h.id) for h in index.search(pack.id, related_query(...), limit=8)]
) -> LawCheck: ...

def related_query(drawing: Drawing, proposal: Proposal) -> str: ...  # the change in words, for LawIndex.search
# LawCheck.related keeps these ClauseViews (they carry `limits`, `drawing_checkable`, ref, law title, url)

def validate_law_note(  # LC-9b, pure: the kept finding with the server-filled clause, or None (dropped)
    note: LawNote, law_check: LawCheck, clauses: Mapping[str, ClauseView], tool_values: Collection[float]
) -> AiFinding | None: ...

class LawCheck(Frozen):  # pack, pack_name, fail_means, findings, unchanged, related, ai_findings, subjects,
                         # subject_values, note (LC-3, LC-5)
    def for_model(self) -> dict[str, Any]: ...  # LC-7: findings without clause quotes
```

`Finding`, `LawNote`, `AiFinding` and `LawCheck` are pydantic `Frozen` models in the same module; field names as in §2.3.
`clauses` for `validate_law_note` = every ClauseView of this turn (`law.related` + the model's `get_clause` results,
by id; a `search_law` hit the model cites is fetched with `index.clause`). The loop keeps the validated notes with
`law_check.model_copy(update={"ai_findings": (*law_check.ai_findings, *kept)})` (LawCheck is Frozen).

## 6. Owners (agreed with the agent-chat orchestrator)

- Law-kb fleet: LC-1 to LC-5, LC-9 (`related_query`, `related` with limits), LC-9b's pure validator
  `validate_law_note(note, law_check, clauses, tool_values) -> AiFinding | None` (signature in §2.4), + `for_model` (`app/core/plan_edit/law_check.py` + tests), on a
  branch from `agent/chat`; its PR targets main after #261 merges.
- Agent-chat fleet (w5:p1): LC-6 to LC-8, LC-9a (prompt + `final_answer.law_notes`), LC-9c, LC-10 to LC-16 in its files (`plan_tools.py`, `app/core/agent/`, `app/api/chat.py`,
  `src/agent/`), when Tudor says go.
- No change to `app/core/checks/` or `backend/app/rules/` (Bogdan's codecheck); if one is needed it goes to #220.
