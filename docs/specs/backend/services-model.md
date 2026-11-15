# Editable services model: pipes, ducts, cables and their terminals as one model the agent can change (spec)

Status: draft, 2026-11-14 evening, by the research lead for Tudor's ifc orchestrator. Contract and reasons: decision
[0017](../../decisions/0017-editable-services-model.md) (proposed). It extends decision
[0013](../../decisions/0013-agent-chat.md) and [docs/specs/agent-chat.md](../agent-chat.md) and changes none of
their rules. Board: #281, #222. Source: Tudor, 2026-11-14: "make sure te approach you are chosing for storing the
information of procssed pipes vents etc, will be able to be modified by the agent with a tool cool, like move
sockets redraw the diagrmams".

Requirement ids SV-n; a test names the id it covers. Numbers marked *measured* come from prototypes on the bench
models (gitignored notes); a public file names no dataset file.

## Alignment with #333 (services-follow, decision 0016), settled on #281 2026-11-14

- #333 (Bogdan's side) owns `core/services/model.py` (`ServiceElement`, `Frame`, `fit_frame`), `core/services/graph.py`
  (`ServiceGraph`), `core/services/follow.py`, `adapters/ifc_services.py`, `adapters/service_tools.py` and
  `Proposal.services: ServicesFollow`. This spec's files are named apart: `core/services/stored.py` (the stored
  model), `core/services/ops.py` (the operations), `derive.py`, `edit.py`, `route.py`.
- This spec's proposal field is `Proposal.services_change` (not `services`).
- SV-32..SV-35 (what a wall edit does to services) are done by #333's `follow` and leave this spec; SV-33's
  `services_check` is #333's `Proposal.services`. #333's re-seat estimate (`follow._reseat`) calls this spec's
  reroute rule (SV-18) once both are merged.
- Later: `ops.py` can be built on `ServiceGraph`, and #333's `ServiceFollower._read` can read the stored model (SV-8)
  instead of the IFC. Neither is needed for either PR to merge.

## Purpose

A person asks the project chat "move this radiator to the window wall" or "what stops working if I take this wall
out". The agent calls tools with ids. Geometry code moves the terminal, reroutes its branch, recounts pipe metres
per size, re-checks that everything is still connected, and returns a proposal with a before/after picture. The
person accepts or rejects. The source file never changes.

For that, the services of one file are stored once as a model, and every count, length and graph answer is
computed from that model, so an edited copy can be recounted the same way.

## Scope

In: services models from IFC (heating, plumbing, ventilation, electrical); the stored model, its derivations, four
edit operations, the tools, the redraw, and what a floor-plan edit reports about services.

Out (v1): editing a model read from a picture (listed and counted only); vertical reroutes and risers; runs
through several rooms; flow, pressure and cable sizing (sizes are copied); clashes with structure and other
disciplines; writing an IFC; `propose_reroute` of an existing run.

## Files owned (new; future workers)

- `backend/app/core/services/stored.py`, `derive.py`, `ops.py`, `edit.py`, `route.py`, `walls.py`: pure (pydantic,
  shapely, no adapter, no settings, no ifcopenshell, no image library).
- `backend/app/adapters/ifc_model/services_model.py`: builds the model from an IFC file.
- `backend/app/adapters/services_store.py` (cache, id map), `services_tools.py` (tools), `services_picture.py`
  (the plan picture of a storey), `backend/app/api/services.py` (the picture route).
- Tests beside them: `backend/tests/test_services_*.py`, on synthetic IFC files built in the test.

Used, not owned (additive changes proposed to their owner, decision 0013's side): `core/plan_edit/model.py`
(`Proposal.services_change`, `Proposal.services_check`), `adapters/plan_tools.py` (`propose_remove_wall` fills
`services_check`), `adapters/agent_tools.py` (offers the tool set, import-guarded like the law tools),
`adapters/chat_rules.py` (keyword rules), `core/agent/loop.py` (step labels), `adapters/ifc_model/facts_mep.py`
(facts from stored elements), `frontend/src/agent/EditCard.tsx` (the overlay layer).

## 1. The stored model

One JSON document per source file. Lengths in metres, model coordinates, z up.

```json
{"version": 1,
 "source": {"kind": "ifc", "sha256": "…", "schema": "IFC4", "architecture_sha256": "…"},
 "connectivity": {"state": "connected", "reason": null},
 "storeys": [{"id": "L2", "name": "…", "elevation_m": 3.75, "frame_m": [10.0, 5.0, 60.0, 40.0]}],
 "elements": [{"id": "E12", "ref": {"guid": "…"}, "kind": "space_heater", "group": "flow_terminal",
               "type": "…", "category": "…", "label": "Radiator 22-600", "typed": true,
               "systems": ["…"], "system_type": "…", "discipline": "heating",
               "storey": "L2", "room": "SR7", "size": null, "length_m": null,
               "at": [12.40, 8.10, 3.90], "body_m": [1.20, 0.06, 0.60],
               "path": null,
               "ports": [{"id": "E12.p1", "at": [11.9, 8.1, 3.9], "flow": "sink"}]}],
 "connections": [{"a": "E12.p1", "b": "E40.p2", "state": "stated"}],
 "rooms": [{"id": "SR7", "ref": {"guid": "…"}, "name": "…", "storey": "L2", "polygon": [[x, y], "…"]}],
 "walls": [{"id": "SW3", "ref": {"guid": "…"}, "storey": "L2", "polygon": [[x, y], "…"], "rooms": ["SR7", "SR8"]}],
 "openings": [{"id": "SO4", "kind": "door", "wall": "SW3", "segment": [[x, y], [x, y]], "sill_m": 0.0, "head_m": 2.1}]}
```

- SV-1 **Elements** are every distribution element and building-element proxy `facts_mep.mep_elements` reads, with
  that function's fields (kind, group, type name, category, typed, systems, storey, size, length, discipline,
  PredefinedType) plus `at`, `ports`, and for segments `path` (the polyline through its ports). A segment may have
  any number of ports (*measured*: 8 pipe segments and 99 of 595 duct segments have three or four).
- SV-2 **Ids**: `E<n>` elements, `E<n>.p<k>` ports, `L<n>` storeys (lowest first), `SR<n>` rooms, `SW<n>` walls,
  `SO<n>` openings; `N<n>` for elements a proposal adds. Prefixes differ from 0013's page ids (`R3`, `W2`) on
  purpose. Element ids come from an append-only id map (`<cache>/<sha256 of the file's name>.ids.json`, GlobalId →
  id; keyed by the name the project knows the file by, since a re-export has new bytes): building the same file twice
  gives byte-identical JSON, and a file re-exported with extra elements keeps every old id.
- SV-3 **Connections** come from `IfcRelConnectsPorts` with ports resolved to their elements through
  `ifcopenshell.util.system` (*measured*: equal to walking the raw relations on 7 models). `state` is `stated` from
  the file, `proposed` when an edit made it, `unknown` when the source cannot say.
- SV-4 **`connectivity`** is computed at build time: `connected` when every system with equipment has its equipment
  and terminals in one component; `partial` with a reason naming what is loose ("12 distribution boards have no
  connected port"); `none` when the file has no port connections. Graph operations and edits that need the
  network refuse on `none`, with that reason (Tudor's decision). On `partial` an operation refuses only when its
  own answer depends on the loose part (orchestrator, 2026-11-14, following Tudor's "refuse with the reason"): one
  that needs equipment (feeds, terminals served, trace, run length from an element, farthest terminal) refuses for
  an element with no connected port or on a piece that reaches no equipment; cut-off needs only the stated flow
  and no open end downstream of the valve (SV-11); controllers-between answers when a path joins its two elements and else refuses: "no connection between
  them in the model"; the other operations answer as on a connected model.
- SV-5 **Rooms, walls, openings** come from the architectural model of the same group when both models share
  coordinates: equal storey elevations within 0.05 m and plan boxes overlapping by half (the bench renderer's
  rule). Spaces are found through aggregation as well as containment. Otherwise the three lists are empty, `room`
  is null, and tools that need a wall refuse: "this services model has no rooms: its building model is missing or
  does not line up with it".
- SV-6 **Page fractions are not stored.** A storey's `frame_m` (the box of its elements and rooms plus a 2 m
  margin) fixes them: `fx = (x − x0) / (x1 − x0)`, `fy = (y1 − y) / (y1 − y0)`, top left origin.
- SV-7 **A model from a picture** (`source.kind: "picture"`): elements have `ref: {page, box, reader}`, `at` in plan
  metres when the sheet has a scale and null otherwise, `ports: []`; runs are elements with a `path` in plan
  metres and `length_m`; `connections` is empty and `connectivity` is `{"state": "none", "reason": "a picture does
  not show which runs are joined"}`. It is built from the picture readers' `PictureReading`
  ([discipline-pictures.md](discipline-pictures.md)); v1 lists and counts it, and refuses graph questions and edits.
- SV-8 **Store**: `<cache>/<sha256>.services.v1.b<builder>.json.gz` beside the fact-sheet cache, written atomically,
  built in the background and never at question time: by the deploy's `python -m app.cli services build`, or,
  for a project file with no stored model, by a capped child process that the first chat turn starts
  (`services_store.ServicesBuilds`, one per app made by `create_app`, one at a time, 3000 MB and 600 s, with
  the project's architecture model when it has exactly one, models read as listing no plan object first; the
  tools say it is being built meanwhile;
  a file with no distribution element stores only a marker, `<sha256>.services.none.b<builder>`, so it is tried
  once, and the tools then say it has no services model; a build that times out or runs out of memory is not
  started again until the backend restarts; 2026-11-15, QA B4 and review of #475). `<builder>` is `services_model.BUILDER_VERSION` (2 since 2026-11-15:
  a model of portless proxies only, a building model's parking marks and trees, is no services model; #503),
  bumped on any change to what the builder writes (also stored as `source.builder`): a model an older builder wrote
  is not served but rebuilt with the saved id map, so a deploy picks up builder fixes and ids survive.
  *Measured*: 1,795 elements → 1.2 MB JSON, 111 KB gzipped, build 15.7 s (10.5 s of it door and window geometry),
  246 MB peak, load 8 ms. Estimated for a 22,600-element model: about 12 MB, 1.3 MB gzipped. A source the reader
  cannot parse has no model, and tools say so.

## 2. Derived, never stored

- SV-9 `derive.facts(model) -> list[Fact]` gives the services topics of the fact sheet (`<kind>.count`,
  `<kind>.length`, `.size_length`, per storey and system, `category.*`, `system.*`, `port.*`, the aggregate topics)
  with the same subjects and values as `facts_mep.mep_facts` on the same file. Test: equal fact lists on two
  synthetic IFC files (IFC2X3 and IFC4). *Measured*: 416 of 416 aggregates equal on the bench heating model.
- SV-10 `derive.graph(model)` is an adjacency over `connections` in plain Python (dict, `deque`, `heapq`; no graph
  library). `ops.py` holds the operations of the earlier plan: terminals served, farthest terminal, what feeds
  an element, trace, run length per system or from a source (optionally per size), controllers between two
  elements, what closing a valve cuts off, storeys of a system, systems crossing storeys, open ends, unconnected
  elements, panel and circuit of a device, system info. A junction is any element with three or more ports.
- SV-11 Definitions the operations must follow, each with a hand-traced test: "what feeds X" returns the set of
  equipment X reaches (not the nearest by hop count), preferring a heat or air source over a pump when both are
  reached; a walk passes through pumps and fans (flow-moving devices sit inline in a run) and stops at any other
  equipment; a heat or air source is known by its IFC class or PredefinedType (energy conversion devices such as
  boilers, heaters, coils, heat exchangers and AHUs; water heaters; storage tanks and pressure vessels, not
  expansion vessels); with no such source the answer is every equipment unit reached, and with no equipment
  reached it refuses: "its network reaches no equipment"; adjacent equipment pieces count as one unit; cut-off needs a stated flow direction on at least 90% of
  the ports of the valve's systems (of its connected piece when it has no system), not connected equipment, so it
  answers on a loose part of a `partial` model too; else it refuses: "this model does not say which way the water flows here".
  On any model it also refuses when an outlet of the valve, or of anything it passes downstream (equipment it stops at
  excepted), is open: "the model does not show what lies downstream of <valve>: at <element> a connection is
  missing"; or is connected with no stated direction on one side (flow "both" or none): "the model does not say
  which way the flow goes at <element>, so it cannot tell what lies downstream of <valve>"; and it never answers "cuts off 0" (a valve with nothing
  downstream along stated flow refuses with the flow reason).
- SV-12 A full re-derive (facts, graph, checks) runs after every edit. *Measured*: 6 ms for 1,795 elements.

## 3. Edit operations (`core/services/edit.py`, pure)

Each takes a model and ids, applies a patch to a copy, and returns a `ServicesChange` or raises `EditRefusedError`
with a plain reason. The input model is never mutated (test: its hash before and after).

- SV-13 `Patch = {moved, removed, added, connections_removed, connections_added, changed}`; `apply(model, patch)`
  is pure. A proposal stores its patch; the model a chat edits is the source model plus the chat's accepted
  patches, in the order they were accepted.
- SV-14 `move_terminal(model, element_id, wall_id, position)`, `position` one of `centre`, `start`, `end`,
  `under_window`, or a point resolved by the server from a selection (SV-22): the terminal is placed on that wall
  of its own room at its old distance from the wall and its old height, rotated to the wall; then the reroute
  (SV-18).
- SV-15 `remove_element(model, element_id)`: a terminal goes with its branch back to the junction, which is
  closed as in SV-18 step 2. *Measured*: 10 of 10 random radiators, every check passing.
- SV-16 `add_terminal(model, like_element_id, wall_id, position)`: a copy of that element's type on the wall,
  connected by the reroute rule to the nearest main of the same system type. *Measured*: 4 of 10 random rooms and
  walls, the rest refused with a reason (wall too short, no free spot, door in the way).
- SV-17 `resize(model, element_id, size)`: `size` must be a size some element of the same system already has; the
  facts move between sizes; the flag "Flow and pressure are not checked." always goes with it.
- SV-18 **The reroute rule** (one rule for pipes and ducts; a junction is any element with three or more ports):
  1. Place: the terminal goes onto a wall of its own room, at its old distance from the wall and its old height,
     at the asked position; if that place is taken it slides in 0.25 m steps. A window is in the way only when
     its sill is lower than the terminal's top plus 0.05 m.
  2. Remove the terminal's branch back to its junction, on each port. A tee fitting left with two ports is
     replaced by a straight piece of the main's size; a tapped segment loses the tap port.
  3. Connection point: the nearest point on a run of the same system, with a cross-section at least the branch's,
     at the old height ± 0.3 m. In this order: a run along a wall of this room (within 0.3 m of the route line), any
     run in the room, the old junction if it is in the room, a run at most 1.0 m outside the room (flagged).
  4. The supply runs along the room's walls, inside the room, at the old wall distance (0.05 m if unknown), the
     shorter way round; the other way when the shorter way passes a door.
  5. The return is the supply path offset to the room side by the old pair spacing (0.06 m if unknown); it is
     never routed on its own. The variants that do not cross are tried first; one crossing within 0.15 m of the
     terminal's ports is allowed and flagged.
  6. The run turns off the wall at the port, not past it. Sizes are copied from the removed branch.
- SV-19 **Refusals** (status `refused`, these words): "This is not a terminal."; "This element is in no room of the
  model."; "It is already on that wall."; "This wall is too short for it." (shorter than its body plus 0.1 m each
  side); "No free place on this wall: a door or another terminal is in the way."; "Another terminal is already
  there."; "Both ways round this room pass a door."; "No pipe of this circuit in or next to this room." (duct,
  cable by discipline); "Its branch does not end at a junction: a valve or equipment is in the way."; "Supply and
  return would cross." (anywhere but at the terminal's ports).
- SV-20 **Flags**: `long_reroute` when the added length is more than three times the removed length plus 2 m
  ("Long reroute: 12.40 m of new pipe replaces 0.50 m."; *measured* old branches: median 0.32 m, 90th percentile
  6.84 m); `through_wall` ("The connection goes through a wall: it needs a core drill."); `crossover` ("Supply
  and return cross at the terminal's connection."); `not_sized` on every move and add ("Sizes are copied from
  the old branch. Flow, pressure and clashes with other services are not checked."); `wet_room` as 0013's AC-19
  when the room is a bathroom, WC or sauna. Code rules are not quoted: the agent may call `search_law`.
- SV-21 **Checks**, recomputed on the copy and returned with the change: the network has as many components as
  before; the terminal reaches the same set of equipment; no other terminal's set changed; no orphaned element;
  open ports unchanged; supply and return do not cross away from the terminal; no door passed. A change with a
  failed check is refused ("The reroute would disconnect …"), never returned.
  *Measured* on the bench's fully connected building, every radiator to a random other wall of its room (63
  moves), rule without the allowed crossover: 23 proposals, all with every check passing, 13 with no flag, 49 ms
  median; refused 40 (15 pair would cross, 9 doors both ways, 8 no run in reach, 8 placement). Twelve random
  proposals judged by eye: 7 look like an engineer's drawing, 4 acceptable, 1 not (a 29 m run, flagged). With the
  crossover allowed (a variant, not yet preferring the clean options): 38 of 63. Air terminals moved 1 m: 10 of
  10, 6 with no flag. The earlier rule that crossed rooms freely gave 46 of 63 but one or two in five looked right:
  topology checks do not judge a drawing, so the rule is strict and the bench judges pictures by eye.

## 4. Tools (`adapters/services_tools.py`, decision 0013's tool form)

`SERVICES_TOOLS` + `run_services_tool(store, name, arguments) -> str`, never raises. Every result with a place has
`drawing_id`, `page` (the storey's ordinal, 1 = lowest) and `box` in page fractions, so the loop mints evidence ids.

- SV-22 A selection on a services picture is 0013's `Selection` (`region` on the drawing and storey page). The
  store resolves it to a room, the nearest wall and a point on it. The model never writes a coordinate or a
  distance.
- SV-23 `list_services(drawing_id, storey?, system?, room_id?, kind?)` → storeys, systems (name, discipline, element
  counts, length), `connectivity`, and the terminals and equipment that match (`id`, kind, label, room, room_name,
  system), at most 60 with a `more` count. With `room_id`: that room's walls (`id`, length, free length, openings,
  what is mounted on it) and whether a main is in reach. The whole result stays under 4,000 characters. `room_id`
  is an id or a room's name, in any case and word order ("küche 1-3" is "1-3 Küche"), else the one room whose
  name holds all its words; several or none is an error naming the rooms (2026-11-15, QA #430). `by_type` and
  `by_room` ("<id> <name>") count every match even when the items are cut, the 30 largest groups and the rest under
  "and K more groups" (fewer when the result would pass 4,000 characters); breakdowns are answered from them
  (2026-11-15, #430 R2). `by_kind` counts them per kind (the IFC class: a water heater, a roof drain or a filter is
  no `sanitary_terminal`), and `kind` narrows the count and every group to that kind (2026-11-15, #430
  c6887184725).
- SV-24 `ask_services(drawing_id, op, element_id?, to_element_id?, system?, storey?, kind?, size?)` with `op` a
  closed list of SV-10's operations → the value, the elements behind it (ids with boxes, at most 30), or
  `{status: "unknown", reason}`.
- SV-25 `propose_move_terminal(drawing_id, element_id, wall_id? | selection_id?, position?)`,
  `propose_add_terminal(drawing_id, like_element_id, wall_id? | selection_id?, position?)`,
  `propose_remove_element(drawing_id, element_id)`, `propose_resize(drawing_id, element_id, size)` →
  `{status: "ok", proposal}`, `{status: "refused", reason}` or `{status: "cannot_edit", reason}` (a picture model,
  no rooms, connectivity `none`). One proposal per turn, as 0013.
- SV-26 The rules model (`chat_rules.py`) gets keyword rules so the no-keys mode and the e2e work: move / relocate
  + radiator, socket, outlet, air terminal, diffuser → `list_services` → `propose_move_terminal`; "what feeds",
  "what does … serve", "what is cut off" → `ask_services`; how many / which + a terminal (also sink, basin,
  toilet) + "in <room>" → `list_services(room_id=<room>, kind)` and the count with the items, or the tool's
  error, only when the project's drawings besides the services model are IFC files (or none: an IFC set aside);
  with a plan or a picture beside it, or a last "in …" naming a floor, a level, the building or "all"/"total", the
  drawings answer as before (2026-11-15, QA #430, #491 review, #430 R3).
- SV-27 Cost: no model call beyond the chat's own steps. *Sourced*: at $1.50 in / $7.50 out per million tokens a
  four-step turn is about $0.03-0.06, inside `AGENT_TURN_USD` 0.10. The six tool schemas together stay under
  1,500 tokens (test: a character count).

## 5. The proposal and the redraw (additive to 0013's `edit`)

```json
"edit": {"proposal_id": "p2", "drawing_id": "…", "page": 2, "state": "proposed",
  "removed": [], "added": [], "rooms": [],
  "unknowns": ["Whether the new run clashes with other services: not checked."],
  "flags": [{"code": "not_sized", "text": "Sizes are copied from the old branch. Flow, pressure and clashes with other services are not checked."}],
  "services_change": {"op": "move_terminal", "storey": {"id": "L2", "name": "…"}, "based_on": ["p1"],
    "picture": "/api/projects/{project_id}/drawings/{drawing_id}/services/L2.png",
    "moved": [{"id": "E12", "label": "Radiator 22-600", "from": [0.41, 0.32], "to": [0.47, 0.38]}],
    "removed": [{"id": "E31", "polyline": [[0.40, 0.31], [0.44, 0.31]], "label": "Pipe DN15, 2.00 m", "system": "…"}],
    "added": [{"id": "N1", "polyline": [[0.40, 0.31], [0.47, 0.31], [0.47, 0.37]], "label": "Pipe DN15, 6.50 m", "system": "…"}],
    "facts": [{"what": "pipe length", "system": "…", "size": "DN15", "unit": "m", "before": 38.50, "after": 43.00}],
    "checks": [{"code": "connected", "ok": true, "text": "The heating network is still in one piece."}]}}
```

- SV-28 `Proposal.services_change: ServicesChange | None = None`. For a services proposal the top-level `removed`, `added`
  and `rooms` are empty, `page` is the storey's ordinal, and `drawing_id` is the services model's drawing.
  Polylines and points are page fractions of the storey picture (SV-6). Metres to 2 decimals.
- SV-29 `GET /api/projects/{project_id}/drawings/{drawing_id}/services/{storey_id}.png` → the storey drawn from the
  stored model (rooms and walls light grey, runs coloured per system, terminals and equipment as symbols with a
  legend), always the source state. 404 unknown, 409 no model. *Measured*: 30-42 ms per storey with PIL.
- SV-30 The frontend edit card draws `services` on that picture as it draws plan edits: removed runs dashed grey,
  added runs thick, a moved terminal as a hollow mark with an arrow to its new place, the facts as "before →
  after" lines, the checks with a tick or a cross in words, then unknowns and flags. Before hides the overlay.
  A halved main is not shown as removed and added. The bench renderer (`plan_picture.py`) is not used here.
- SV-31 Accept and Reject are 0013's route. Accept marks the proposal accepted and adds its patch to the chat's
  accepted list (SV-13). The project's fact sheet and every answer outside the chat stay the source's.

## 6. What a floor-plan edit says about services

- SV-32 `walls.services_at(model, storey_id, polygon_m) -> WallServices`, pure: for a wall strip in model metres,
  the elements **mounted on** it (a terminal within 0.10 m of a face and parallel to it), the runs **crossing** it
  in plan with their height relative to the storey (under the floor, in the room, above the ceiling when the
  model's ceiling height is known), the runs **along** it (within 0.10 m of a face for more than 0.5 m), and, per
  discipline, how many terminals lose their supply if the crossing runs are cut (the graph's count).
  *Measured*: about 50 ms per wall for three disciplines.
- SV-33 `Proposal.services_check: {status: "checked" | "not_checked", reason, affected: [{id, kind, label,
  relation, system, box}], lost: [{discipline, terminals, elements}]} | None`. `propose_remove_wall` fills it.
  `checked` only when the plan page is a sheet of an IFC building model and the project holds services models
  that line up with it (SV-5). A PDF or scanned plan, a services drawing on another sheet, or no services model:
  `not_checked` with the reason in plain words. The edit card's note "Structure, services and permits are not
  checked." then keeps or drops the word "services" accordingly.
- SV-34 A wall removal is never refused or changed because of services. The proposal gets one flag ("2 radiators
  hang on this wall and 2 heating pipes cross under it; cutting them would leave 5 radiators without supply.") and
  the unknown "Whether the crossing pipes are inside the wall or pass under it: the model does not say."
  *Measured*: 85% of 52 inner walls have a crossing in plan, all under the floor or above the ceiling.
- SV-35 Moving the affected terminals is a second proposal the person asks for; it is computed on the source plus
  accepted patches like any other.

## 7. Tests

- Core, synthetic models built in the test (two rooms, one wall with a door, a boiler, a main along one wall, two
  radiators on tees): SV-2 id stability; SV-9 fact equality; SV-10/11 each operation with a hand-traced answer;
  SV-14..17 each edit with facts before/after equal to the geometry's lengths and every SV-21 check; each SV-19
  refusal; SV-18's door and room rules; the input model's hash unchanged.
- Adapter: build from a synthetic IFC4 and IFC2X3 file; a file with no ports gives connectivity `none`.
- Tools: each tool through `run_services_tool` with a bad id, a refusal and a success; result length; SV-22.
- API: the picture route; a chat turn with `CHAT_MODEL=rules` that moves a radiator end to end, accept, a second
  move computed on the accepted state.
- Bench (local, not CI): every terminal of the fully connected bench models moved to a random other wall; the
  report states proposals, refusals by reason, flags, and twelve pictures judged by eye. Demo cases come from the
  unflagged set.

## Open decisions

1. Who owns the additive changes on 0013's side (`Proposal` fields, `propose_remove_wall`, `agent_tools.py`,
   `chat_rules.py`, the edit card): asked on #281.
2. Whether `facts_mep` reads the stored elements (one reader, recommended) or both paths stay with an equality
   test.
3. Electrical: no bench building has connected circuits, so sockets move with a cable only on a model that states
   them; otherwise a socket moves as a point with the unknown "its cable is not in the model".
4. Whether accepted patches should also change the project's answers outside the chat (0013 says no).
