# 0016: Building services are kept as one editable services model per file; facts and graph answers are derived from it, and the agent changes it only through id-based tools that return proposals

- Status: proposed
- Date: 2026-11-14, evening (Europe/Helsinki)
- Decided by: Tudor ("also look into the feature we are making to modify floor plan and then modify the piping and
  heating and vents. make sure te approach you are chosing for storing the information of procssed pipes vents etc,
  will be able to be modified by the agent with a tool cool, like move sockets redraw the diagrmams idk",
  2026-11-14 ~22:10 by the orchestrator's log; also: the planner model is `gemini-4-hydrogen`, and broken
  connectivity is refused with the reason). Shape and rules: agent research lead (worker) for Tudor's ifc
  orchestrator, from four prototypes run on the bench models.
- Board thread: #281 (discipline facts), #222 (agent chat tools and geometry)
- Behaviour, signatures and tests: [docs/specs/backend/services-model.md](../specs/backend/services-model.md)

## Context

- Today a services IFC model is read into a fact sheet of aggregates (`facts_mep`), and a graph prototype answers
  "what does this unit serve" from port connections. Both are read-only views built straight from the file, so
  nothing an agent could change exists, and a change could not be re-counted.
- Decision [0013](0013-agent-chat.md) already fixes how the chat edits floor plans: tools take and return ids, geometry
  code computes, an edit is a proposal on a copy that a person accepts or rejects, the source file never changes,
  and every number in the answer comes from a tool result of the turn.
- Measured on the bench's fully connected heating model (1,795 elements): one JSON document of 1.2 MB (111 KB
  gzipped) reproduces all 416 fact aggregates and every graph answer checked; loading takes 8 ms and a full
  re-derive 6 ms; moving a radiator with reroute, re-derive and checks takes 49 ms (median of 63).
- Measured on the same building: about 85% of inner walls have a pipe or duct crossing them in plan, every one of
  them under the floor or above the ceiling; refusing a wall removal for that would block most walls.
- The chat model's price is now published: $1.50 in / $7.50 out per million tokens, thinking billed as output and
  not switchable off (vendor page, read 2026-11-14). A separate planner call would cost $0.004-0.02 and 6-12 s.

## Decision

1. **One services model per source file** (`app/core/services/model.py`, pure): storeys, elements with stable short
   ids (`E12`, mapped to the IFC GlobalId or to a picture spot), kind, type, systems, size, length, position and
   ports in model metres, connections between ports with a `state` (`stated`, `proposed`, `unknown`), and the
   rooms, walls and openings of the building's architectural model when both share coordinates. It is a JSON
   document, version-numbered, cached by the source file's sha256 beside the fact sheets, with an append-only id map
   so ids never shift.
2. **Everything else is derived from it**: the services facts of the fact sheet and the graph operations are pure
   functions of the model, recomputed in full after every edit (milliseconds at these sizes). `facts_mep` keeps its
   topics and values; the equality of both paths on the bench models is an acceptance criterion.
3. **The same model from IFC and from pictures.** A picture gives elements with page spots, counts and plan
   lengths; its connections are `unknown`, so graph questions and edits on it are refused with that reason.
4. **Edits are tools in the agent chat, in 0013's form**: `list_services`, `ask_services`,
   `propose_move_terminal`, `propose_add_terminal`, `propose_remove_element`, `propose_resize`. Arguments are ids
   and closed choices only (an element, a wall, a selection the person drew, a position word); no coordinate, no
   free distance. Each `propose_*` applies a patch to a copy and returns a proposal: what moved, what was removed
   and added, the recomputed facts before and after, the graph checks, what is unknown, and flags.
5. **A proposal is 0013's `edit`, with two additive fields**: `services` (a services change: polylines and points
   in page fractions of the storey's picture, facts, checks) and `services_check` (what a floor-plan edit does to
   the services: affected elements and how many terminals lose supply, or "not checked" with the reason). Accept
   and Reject are 0013's. An accepted services proposal stays a patch of the chat; the next proposal of that chat
   is computed on the source plus the accepted patches.
6. **A wall removal flags services, never refuses and never moves them.** Stated as fact: terminals mounted on
   the wall, runs crossing it in plan with their height, and the downstream loss. Unknown: whether a crossing run
   is inside the wall. Checked only when the plan and the services come from IFC models of one building with shared
   coordinates; every other combination says "services not checked".
7. **Reroute by one simple rule or refuse**: a moved terminal's branch is removed back to its junction and a new
   pair is routed along the walls inside its room to the nearest main of the same system; a new run stays inside
   the room (one flagged step to a main just outside it) and never passes a door. Anything the rule cannot do is a refusal with a plain reason; a long or
   unusual result is flagged. Sizes are copied; flow, pressure and clashes are named as unknown.
8. **Redraw**: the backend draws one plan picture per storey from the model (not from the IFC); the frontend draws
   the change on top of it as an overlay, as it does for plan edits. Before hides the overlay.
9. **No separate planner call.** Services questions and edits run as tools inside the chat turn the agent
   already makes. The batch answering path (dataset questions) stays template-only and free.

## Alternatives considered

- Keep fact sheet and graph as two read-only views of the IFC: nothing to edit, and an edit could not be
  re-counted without rewriting the IFC.
- Write a patched IFC per proposal (IfcPatch / ifcopenshell API): a 13-32 s parse and up to 1.3 GB per edit on the
  large bench models, against 65 ms on the JSON model; and 0013 says the source file never changes.
- Let the model write IfcOpenShell code: the best model scores 49.5 of 100 on BIM-Edit and none fully solves more
  than 3.4% of tasks (arXiv 2606.20146, read 2026-11-14).
- A graph database: the largest bench model is an estimated 12 MB of JSON (1.3 MB gzipped), and a trace takes
  under 1 ms in memory.
- One combined plan + services proposal: the plan edit must still work on scans and PDFs, where no services check
  is possible, and moving a terminal is its own choice with its own Accept.
- Reusing the bench renderer for before/after: it draws from IFC-derived objects and cannot show removed, added or
  moved items.

## Consequences

- New: `app/core/services/` (model, derive, graph, edit, route, walls), `app/adapters/ifc_model/services_model.py`,
  `app/adapters/{services_store,services_tools,services_picture}.py`, `app/api/services.py`, one frontend overlay
  layer. Shared with 0013's owner, additive only: two optional fields on `Proposal`, the tool set in
  `agent_tools.py`, keyword rules in `chat_rules.py`, step labels in the loop, and the affected-services call in
  `propose_remove_wall`.
- The graph operations of the earlier plan move into `app/core/services/graph.py` and read the model, not the IFC.
- Honest limits to state: on the bench heating model, 23 of 63 random radiator moves (37%) gave a proposal, every
  one passing every check, 13 with no flag; 7 of 12 judged by eye looked like an engineer's drawing and 11 of 12
  were acceptable. A looser rule gave 46 of 63 but one or two in five looked right, so the strict rule stays and
  the rest are refusals with a reason. Allowing the crossover at the radiator raises it to 38 of 63 (variant, not
  finished). Air-terminal moves 10 of 10, removals 10 of 10. Sockets are untested: no bench building has
  electrical connections.
- Settings: `AGENT_PRICE_OUT_PER_M` can drop from the 9.00 placeholder to 7.50.
- Revisit if models much larger than 10^5 elements arrive (then a database), if users need vertical reroutes or
  several rooms per run (then a real router), or if accepted patches must be exported (then IFC writing).
