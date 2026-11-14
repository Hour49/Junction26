# 0016: A plan edit proposed in the chat is followed through the building's service models by geometry and graph code, and the result rides on the proposal

- Status: proposed
- Date: 2026-11-14 21:45 (Europe/Helsinki)
- Decided by: Bogdan ("when I want to modify one floor plan, for it to modify all the plumbing plan, electrical
  grid, ventilation etc everything together", 2026-11-14 ~20:30; "please coordinate with tudor. he is building
  the tools which will understand the pipes vents etc", ~20:50). Design and build by agent multi for Bogdan's
  orchestrator, who approved the design (20:41) and the one-tool shape (20:44).
- Board thread: #281 (the services graph, with Tudor's IFC side), #222 (decision 0013's tools)
- Behaviour, rules and tests: [docs/specs/backend/services-follow.md](../specs/backend/services-follow.md)

## Context

The chat proposes plan edits by geometry (decision 0013): a wall strip removed, a room carved out. A building
also has plumbing, ventilation, heating and electrical models, and an edit that looks fine on the architectural
plan can leave fixtures without water or put a wall across a duct. #311 reads the service models as facts (how
much of what); nothing related them to the plan's walls and rooms.

Checked on an open building with separate architectural, sanitary, ventilation and heating models (DigitalHub
v2, RWTH Aachen, MIT): the sheet rendered from the architectural model and the three service models are one
coordinate frame (22 rooms fitted, worst 2 mm off); a service model reads as plain data in under a second
without meshing; no file states which wall or room a service element belongs to, so that has to be computed.

## Decision

1. **The follow-up is computed, never generated.** For every proposal, code tests each service element against
   the proposal's removed and added geometry (on the strip, inside it, through it, an upright run in it) and
   asks the model's own port graph, per system, which terminals are no longer connected to the rest. No model
   call, no image generation.
2. **It rides on the proposal.** `Proposal.services` (additive, null when off) carries one entry per lane
   (plumbing, ventilation, heating, electrical), always all four: a lane without a model says so. The plan
   tools attach it to every proposal they make, after the law check, without touching the proposal's rooms,
   removed or added pieces. One proposal per turn stays as it is.
3. **One tool for the model.** The model picks the edit with the existing plan tools; the server follows it.
   There is no separate tool to forget or to call in the wrong order. The tool result gives the model each
   lane's line and actions in plain words with their numbers, and no ids or places (0013 §2).
4. **A proposal, never a verdict.** Each consequence has a status: `follows` (a rule resolved it), `stays`,
   `needs_decision` (with the reason), `cut_off`. Nothing is called approved, blocked or coordinated. Fixed
   unknowns say what is not checked (services against each other in 3D, sizes, flows, waste falls).
5. **The graph is a core module others ask.** `app/core/services/graph.py` (`ServiceGraph`: ids in, typed
   results out) is what the follow-up uses and what read-only questions ("what feeds this radiator") can use.
6. **By setting.** `SERVICES_FOLLOW=off|on`, default off. Off: no model file is opened and `services` is null.

## Alternatives considered

- Separate tools per discipline that the model orchestrates: more visible steps, but an edit could be shown
  without its consequences when the model skips one (pi-spike's finding; the orchestrator chose one tool).
- Reading the relations from the files (hosted-by, contained-in-space): the open models surveyed state none;
  everything is contained in the storey.
- Testing against the IFC wall objects: one IfcWall runs past several rooms (up to 63 m in the test building);
  the unit of an edit is 0013's strip between two rooms.
- A threshold that calls a wall "not removable": a judgment the data does not carry. The facts are stated.

## Consequences

- Works only where a sheet was drawn from a building model that is in the project (the model route) and the
  service models share its storeys. Scans, photos and drawn PDFs without a model: every lane says "not checked".
- Reading a service model keeps about 0.2 GB that ifcopenshell does not give back; the last 8 read models are
  kept as plain data. A model over 150 MB is not followed.
- Electrical models seen so far carry points only (no circuits): sockets and lights can be re-seated, cable
  routes cannot be followed. No electrical model with a clear licence is in the demo data yet.
- New: `app/core/services/`, `app/adapters/ifc_services.py`, `app/adapters/service_tools.py`, setting
  `SERVICES_FOLLOW`, `Proposal.services` in the OpenAPI document, `frontend/src/agent/multi/`.
- Revisit when a second discipline's change must trigger a third (a re-routed duct needing an opening in a kept
  wall), or when an accepted proposal should be written back as a model.
