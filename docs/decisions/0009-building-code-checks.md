# 0009: A building-code pre-check is a rule pack as data, checked over the drawing model, served per drawing

- Status: accepted
- Date: 2026-11-14 12:29 (Europe/Helsinki); amended the same day after the frontend review (12:36) and the
  dev-drawing runs (12:42, 12:51)
- Decided by: agent codecheck, accepted by the orchestrator 2026-11-14 12:29 ("0009 accepted, GO"); story #139
  (Bogdan, 2026-11-14 12:20: MUST DO). Review items 1-13 by Tudor's fleet, all accepted by the orchestrator
  (12:36). "A check FAILS only on reliable inputs; otherwise cannot tell, with the reason" (orchestrator, 12:51).
- Board thread: posted by the orchestrator (with 0008, whose `code_check_failed` issues come from here)

## Context

Key value 4 "Rules" (#26) had nothing behind it: the country picker ran on `PENDING_COUNTRY_RULES` in
`frontend/src/shell/pending.ts`. The drawing model has rooms with types and areas, doors and windows with boxes,
and the scale (`app/core/drawing/model.py`), so a check is a comparison over what was read. Every limit must quote a
clause someone read; a missing scale or quantity is "cannot tell", never a guess. This is a pre-check of a few
rules, not a compliance certificate, and every response says so.

## Decision

**Pack format** (data, `backend/app/rules/<pack id>.json`, one per law; `RULE_PACKS_DIR`; loaded and validated at
start by `app/adapters/rule_packs.py`, model `app/core/checks/model.py`):

```json
{
  "id": "fi", "country": "FI", "country_name": "Finland",
  "name": "Finland: homes and accessibility decrees", "law": "Rakentamislaki 751/2023; decrees ...",
  "version": "2026-11-14", "fail_means": "It would not meet today's rule for a new building.",
  "rules": [{
    "id": "fi-habitable-room-window", "title": "A bedroom or living room has a window",
    "op": "room_windows",
    "applies_to": {"room_types": ["bedroom", "living"], "skip_labels": ["R", "RT", "ALKOVI"], "note": "..."},
    "comparison": ">=", "limit": 1, "unit": "count",
    "clause": {"ref": "... 1008/2017, 5 § 1 mom.", "url": "https://www.finlex.fi/fi/lainsaadanto/2017/1008",
               "quote": "Asuin- ja, majoitustilan ikkunan valoaukon on oltava vähintään 1/10 huonealasta.",
               "quote_en": "The light opening of the window ... at least 1/10 of the room area."}
  }]
}
```

- `country` is ISO 3166-1 alpha-2 (the flag), `country_name` what the picker writes, `name` the pack's display
  name (review 1). A pack for one canton says so: `ch-zh` is "Canton of Zürich", never "Switzerland".
- `op` is the machine check type, never shown; `comparison` is machine (`>=`, `>`, `<=`, `<`) and the API adds
  `comparison_text` ("at least", "more than", "at most", "less than") for the screen (review 4).
- `applies_to` uses the drawing model's words (review 5): `room_types` (as `MarkView.room_type`), `element_classes`
  (`door_width`: always `["door"]`), `not_room_types` (`door_width`: doors meeting such a room are skipped),
  `skip_labels` (room ops: a room so labelled is skipped, compared as the takeoff compares names), `note`.
- `clause.quote_en` is null when the law is in English; the screen then shows `quote` alone (review 6).
- The loader refuses a pack (the app does not start) with a rule that has no `clause.ref`, an https `clause.url`
  or `clause.quote`; an unknown op, comparison or room type; a room op without room types; a `door_width` that is
  not a minimum or not `["door"]`; a takeoff rule whose unit is not its key's; repeated ids; an id that is not the
  file name.

**Ops** (`app/core/checks/check.py`, pure, over the `Drawing` and its takeoff):

- `room_area`: each room of the types (indoor, not skipped), its `area_m2` against the limit.
- `room_windows`: each such room, the windows whose box is within 0.35 m of the room's outline (1% of the page's
  long side without a scale); on a sheet drawn from a building model whose space carries `attrs.windows`, the
  model's count, with the drawn windows as marks. A count under the limit is cannot tell when a door of the room
  opens to a balcony or straight outside (it may be glazed), whether the count is drawn or the model's (tuwien's
  "Zimmer" rooms: no IfcWindow, a 2.36 m door to the outside; orchestrator, 2026-11-14).
- `door_width`: each door meeting a room of `room_types` and none of `not_room_types`; its width is the long side of
  its symbol's box at the scale, or the model's `width_m`. The symbol bounds the clear opening from above: more
  than 0.03 m (drawing error) under the limit fails; at least 0.10 m (our frame allowance, not the law's) plus
  0.03 m over it passes; between is cannot tell.
- `takeoff`: one takeoff key against the limit, for the whole sheet.

**Cannot tell**, always with the reason in `why`; never a fail on an input not reliable enough (12:51):

| Case | Why it cannot fail |
| --- | --- |
| The class was not read (`Drawing.read`), a drawing of totals only, a model file with no sheet | nothing to compare |
| A room with no area; a door with no scale, or an element with no position (`attrs.located` false) | no value |
| A door on an `estimated` scale | the raster route estimates that scale from the doors themselves |
| An estimated area whose band reaches the limit, or with no stated error; any estimated area under the limit | estimate |
| Route `raster`, or a route not known (taken as a picture; S2, 2026-11-14): a room under the limit from a read outline (a printed area still fails); a room with no window found; any door box, narrow or wide (S3, 2026-11-14) | read off a picture: 0 of 9 area fails and 1 of 10 window fails on the dev drawings were real; a detector's door box is not a measurement in either direction |
| A room with no window (drawn, or the model's count) but a door to a balcony, an outdoor room, or to no room at all | the door may be glazed (478 of 516 Swiss rooms with no window near shared a door with a balcony) |
| No room of the kinds a room rule names, but rooms of a kind we could not tell (`other`: the label matched no word); for a door rule, the same with no room of its kinds at all (S1, 2026-11-14) | they may be bedrooms (vitoria's HAB1 and SAL rooms, gdynia's "Room 1.3") |
| A room with no window on a sheet drawn from a building model whose spaces carry no window count | 54 of Warmond's 110 IfcWindows have no shape and are not drawn |
| A takeoff quantity two methods dispute with no rule deciding, or that rests on an estimate | no single value |

A rule whose drawing has nothing it applies to (no bedroom; no door into a habitable room) is `not_applicable`,
not cannot tell (review 9). That is said only when no room of the drawing could be of a kind the rule names: rooms
typed as a known other kind (a store, a hall) are not applicable, rooms of a kind we could not tell are cannot tell
(S1). A building model file whose sheets are in the project (a sheet's group holds it and was read from it) is
`not_applicable`, "checked on its sheets"; a model with no sheet in the project stays cannot tell (N3, 2026-11-14).

**API** (additive to v1; docs/API.md "Building-code checks", `openapi-v1.json`, fixtures `checks.json` and
`project_checks.json` appended last; `info.json` gains `rule_packs` at its end):

- `GET /api/info` gains `rule_packs: [{id, country, country_name, name, law, version, note, fail_means, rules:
  [{id, title, op, applies_to, comparison, comparison_text, limit, unit, key, clause}]}]`. `note` is always "A
  pre-check of a few rules, not a compliance certificate." No pack is preselected; choosing none is valid and
  checks nothing (review 2). One pack at a time (review 3).
- `GET /api/drawings/{drawing_id}/checks?pack=fi&project=<project_id>` returns `{drawing_id, file, file_id, pack,
  note, status, rules: [RuleCheck]}`. `file` and `file_id` are this project's upload (review 8); without
  `project`, the stored name and null. `RuleCheck = {rule_id, title, status, why, clause, results}`;
  `CheckResult = {id, rule_id, status, subject: {kind: room|element|sheet, ref, label}, value, limit, unit,
  comparison, comparison_text, why, quantity, marks}`; `CheckMark = {page, box, polygon, ref, label, role:
  subject|counted, quantity, mark_id}`.
- Statuses (review 9): a result is `pass | fail | cannot_tell`; a rule, a drawing and a project are that or
  `not_applicable`: fail when one fails, else cannot tell when one cannot, else pass, else not applicable.
- Ids and links (reviews 10, 11): `CheckResult.id` = `<rule_id>:<room or element id>` (`:sheet` for a takeoff
  rule), stable for the same drawing. `quantity` is the subject's takeoff row (`Row.key`: a room's own area row,
  else its type's count; a door's `door` row), null when the takeoff has none. A mark's `mark_id` is its
  `MarkView.id` in its own row `quantity` (`m<n>` counted, `x<n>` left out by the rule), null when no row has it:
  no second id scheme.
- Units (review 13): `m2`, `m`, `count`, the takeoff's units. `value` is null when nothing was measured; a value
  too uncertain to judge is kept with `cannot_tell`. Values are rounded to 0.001.
- `GET /api/projects/{project_id}/checks?pack=fi` returns `{project_id, pack, note, status, drawings:
  [DrawingChecks]}` in the project's drawing order, each with this project's `file` and `file_id` (review 7).
  409 `not-allowed` while the project is not `done`, as the project's questions answer (review 12); a drawing's
  own checks answer as soon as the drawing exists.
- `pack` is required. An unknown pack is 404 with its own code `unknown-pack` (the hyphenated style of every other
  code), so the screen resets the picker; an unknown drawing or project stays 404 `not-found`.

**Issues (0008):** each `CheckResult` with `status: fail` is one issue of kind `code_check_failed`: drawing,
page, box and polygon from its first `subject` mark, `mark_id` and `quantity` from it, `why` = its `why` plus the
clause ref, state `open`, source ref `<pack>:<CheckResult.id>`. Cannot tell is not an issue. The feed lists them
only with `?pack=` (the country is a screen choice, not stored on the project); it finds the pack with
`app/api/checks.py` `find_pack` (what `pack_of` uses), so an unknown pack is the same 404 `unknown-pack`.

Checks read the drawing as ingest read it; the surveyor's review edits don't change them in this version.

## Measurements behind the holds (dev split only, 2026-11-14)

fable-rooms ran the engine on the pipeline's dev drawings (run `pipeline-bd2471f-20261114-101635`, 69 CubiCasa, 58
Swiss, 44 IFC) before the holds and looked at every fail: CubiCasa room area 9 fails, 0 real (outlines too small,
wrong room type, alcoves); CubiCasa windows 10 fails, 1 real (detector missed windows, misplaced outlines, a glazed
door to the outside); Swiss doors 57 fails, the widths right but 20 of 26 looked at were balcony door leaves (a
two-leaf door read as two); IFC windows held (unshaped IfcWindows are not drawn). On the gold dev sheets, 188 of
190 CubiCasa `living` rooms under 7 m2 were dining labels (R, RT, RUOK, RUOKAILU), and a bedroom's nearest window
is within 0.05 m or far off (0.1-2% between 0.05 and 0.6 m), so the 0.35 m slack decides nearly every room.

After the holds (codecheck, same run, all 171 drawings, `fi` pack):

| Route | Rule | pass | cannot tell | fail | real |
| --- | --- | --- | --- | --- | --- |
| raster (91) | room area | 250 | 49 | 0 | |
| | window | 283 | 16 | 0 | |
| | door width | 0 | 247 | 0 | |
| vector (36) | room area | 94 | 0 | 0 | |
| | window | 91 | 3 | 0 | |
| | door width | 24 | 86 | 6 | 6 |
| IFC (44) | room area | 66 | 0 | 0 | |
| | window | 23 | 43 | 0 | |
| | door width | 4 | 0 | 0 | |

Raster doors after S3 (2026-11-14): the 13 passes there were before are cannot tell. The IFC rows are before #162
(spaces' window counts); on #162's extraction the 44 IFC sheets give area 219/0/8, window 223/4/0, door 96/0/0
(pass/cannot tell/fail; the 8 area fails are a 6.83 m2 bedroom on 4 storeys of the two vitoria models).

"Real": the gold drawing's door or room at the same place (overlap IoU at least 0.3) fails too. The 6 are kitchen
doors of 0.70-0.76 m on two Swiss plans: real as drawn under the Finnish rule.

## Alternatives considered

- A rule as a free takeoff-key expression only: the takeoff has no per-room window count or door width, and a
  check per room needs the room's own mark for the issue feed. Four fixed ops cover the read clauses; `takeoff`
  keeps the generic case.
- One result per rule (worst room): the issue feed and the plan need each failing room placed on its own.
- Checks computed at ingest and stored: a pack can change after ingest; the check is cheap and pure.
- Fail on every input and say how sure: a fail is what a person acts on, and on picture-read inputs most fails were
  the reader's errors, not the plan's.
- The door bands without the 0.03 m drawing error (fail under 0.80, pass from 0.90): the box of a drawn symbol is
  not exact; the error only moves cases to cannot tell, never to a wrong fail. The 0.77/0.93 m bands were accepted
  by the orchestrator on 2026-11-14: "your door limits 0.77/0.93 m are accepted (they only widen 'cannot tell')".

## Consequences

- The frontend gets the country picker, a checks view and failing items to mark from one call per drawing; the
  mock in `frontend/src/shell/pending.ts` can go.
- Adding a country is a JSON file with read clauses; a new kind of quantity is a new op with tests.
- On picture-read drawings most fails become cannot tell until the readers improve (printed areas from labels,
  outlines, windows): reader owners have the cases above.
- The IFC window count needs the IFC adapter to put `windows` on each space's `ModelObject.attrs` (fable-rooms);
  until then those rooms are cannot tell.
- Revisit if review edits must change checks, or a rule needs a quantity a plan does not show (window glass area
  needs heights; a whole-dwelling guard for the dwelling-area and toilet rules).
