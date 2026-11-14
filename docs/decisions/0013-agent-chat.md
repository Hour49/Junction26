# 0013: The project chat is a tool-calling agent whose plan edits are proposals computed by geometry code

- Status: proposed
- Date: 2026-11-14 17:15 (Europe/Helsinki)
- Decided by: Tudor ("the main thing we want is to be able to modify floor plans … the ai agent should then create a
  modified floor plan on that specification requested"; model: "use gemini 4 hydrogen"; 17:05 "go"), agent
  agent-chat orchestrator
- Board thread: #222 (tools and geometry with Bogdan's side), #220 (tool format)
- Behaviour, screens and tests: [docs/specs/agent-chat.md](../specs/agent-chat.md)

## Context

The project chat answers one question at a time through `POST /api/projects/{id}/ask` and cannot edit a plan. We
checked prior art (no product edits an existing plan by chat and keeps true areas; image models invent geometry)
and ran the edit on real data: removing the wall between Bagno 1.01 and Stanza 1.02 on
`site980_bldg2055_floor9178` with our reader's room polygons gives one 24.69 m² room (7.56 + 16.48 + 0.65 m² wall)
in 0.14 s. The pieces exist: `pipeline_tools.py` (#228, list_drawings … get_plan_geometry with `walls_drawn`),
`law_tools.py` (branch laws/knowledge-base), evidence tools (Bogdan's side, ADR 0012), the spend guard (#225).
Research reports: `.agents/research/ac-{code,prior,agent}.md` on Tudor's machine (not in the repo).

## Decision

1. **One agent loop in core** (`app/core/agent/`): a `ChatModel` port (OpenAI chat-completions shape), a toolbox
   of tool modules that each export `TOOLS` + a dispatcher `run(store, name, arguments) -> str` that never raises
   (format agreed on #220), at most 8 model steps and 4 tool calls per step per turn, and a spend cap per turn
   (`AGENT_TURN_USD`, default 0.10) on top of the process spend guard (`app/core/spend.py`).
2. **The model never writes coordinates, file names, pages or boxes.** Tools return ids (`R3` rooms, `W2` walls,
   `sel_1` the user's selection, `ev_4` evidence) and the server resolves them to geometry and places.
3. **"I don't know" is enforced in code.** A turn ends only through the `final_answer` tool
   (`kind: answer | dont_know | conflict | needs_input | edit`). Before a turn is returned the server checks that
   every evidence id was produced in this turn and every number in the text appears in a tool result of this turn;
   a failed check gets one retry, then the turn becomes `dont_know`. Steps, spend or time running out also end in
   `dont_know` with the reason.
4. **Plan edits are proposals.** Plan tools (`app/adapters/plan_tools.py` over pure geometry in
   `app/core/plan_edit/`, shapely) apply an operation to a copy of one page's rooms and drawn walls, compute areas
   in m², and return a proposal with the removed and new geometry in page fractions. No tool writes a drawing; a
   person's Accept marks a proposal accepted (it stays a proposal of the chat, the drawing file is unchanged).
   Whether a wall is load-bearing is `unknown` unless the source says so (IFC `LoadBearing`); the tool and the
   answer say so.
5. **Conversation state is kept on the server** (`<projects_dir>/<pid>/chats/<chat_id>.json`), assistant messages
   stored verbatim: Gemini 3+ needs each tool call's `extra_content` thought signature sent back unchanged.
6. **Model by setting.** `CHAT_MODEL=gemini|rules|off` (default `rules` in tests and no-keys mode, `gemini` on the
   deploy). `gemini` speaks Gemini's OpenAI-compatible endpoint with `AGENT_MODEL` (Tudor chose Gemini 4 Hydrogen;
   its id comes from Bogdan's side, #222) and charges the spend guard after every call with
   `AGENT_PRICE_IN_PER_M` / `AGENT_PRICE_OUT_PER_M`. `rules` is a deterministic planner without a model (keyword
   rules → tool calls), so the chat, its e2e and the demo work with no key. `off`: the frontend keeps today's
   `/ask` chat.

### API (additive to v1)

`POST /api/projects/{project_id}/chat` body `{chat_id?: str, message: str (1..2000), selection?: Selection[]}`
→ 200 `ChatTurn`. 404 unknown project or chat, 409 project not done, 422 bad body, 503 `CHAT_MODEL=off`.

```json
{
  "chat_id": "c3f9a1b2c4d5", "turn": 2,
  "kind": "edit",
  "text": "Removing the wall between Bagno 1.01 and Stanza 1.02 makes one room of 24.69 m² (+0.65 m²) [1].",
  "evidence": [{"n": 1, "id": "ev_1", "drawing_id": "…16 hex…", "name": "Drawn plan 1", "page": 1,
                "box": [0.31, 0.22, 0.38, 0.29], "label": "Bagno 1.01", "sure": true}],
  "edit": {
    "proposal_id": "p1", "drawing_id": "…", "page": 1, "state": "proposed",
    "removed": [{"id": "W4", "polygon": [[0.40, 0.20], [0.41, 0.20], [0.41, 0.30], [0.40, 0.30]],
                 "label": "Wall W4, 2.87 m, 0.12 m thick"}],
    "added": [],
    "rooms": [{"id": "R1+R2", "label": "Bagno 1.01 + Stanza 1.02", "polygon": [[0.30, 0.20], "…"],
               "area_before_m2": 24.04, "area_after_m2": 24.69, "was": ["R1", "R2"]}],
    "unknowns": ["Whether wall W4 is load-bearing: this drawing does not say."],
    "flags": [{"code": "wet_room", "text": "A bathroom changes: in Finland a certified wet-room supervisor inspects the waterproofing."}]
  },
  "options": null,
  "steps": [{"n": 1, "tool": "get_plan_geometry", "label": "Read the rooms and walls of Drawn plan 1", "status": "ok", "ms": 40},
            {"n": 2, "tool": "propose_remove_wall", "label": "Removed wall W4 between Bagno 1.01 and Stanza 1.02", "status": "ok", "ms": 120}],
  "model": "rules", "cost_usd": 0.0, "latency_s": 0.3
}
```

`Selection` = `{id: "sel_<n>", kind: "room" | "region", drawing_id, page, ref?: room id, box?: [x0, y0, x1, y1]}`
(page fractions). `kind` = `answer | dont_know | conflict | needs_input | edit`; `options` (needs_input) =
`[{label, message}]`; `edit` is null unless `kind == "edit"`.

`POST /api/projects/{project_id}/chat/{chat_id}/proposals/{proposal_id}` body `{action: "accept" | "reject"}` → 200
the proposal with its new `state`; 404 unknown, 409 already decided.

### Tools (names final, #222)

- Pipeline (Bogdan's side, as merged in #228): `list_drawings`, `ask_drawings`, `get_takeoff`, `list_conflicts`,
  `list_issues`, `run_checks`, `get_plan_geometry`.
- Laws (Tudor's laws fleet, when merged): `search_law`, `get_clause`. Evidence (Bogdan's side, when merged):
  `search_evidence`, `get_evidence`.
- Plan (ours): `list_walls(drawing_id, page)` (walls with ids, length, thickness, the rooms on each side, doors in
  it), `propose_remove_wall(drawing_id, page, wall_id | room_a + room_b)`, `propose_room(selection_id, name)`.
- Loop (ours): `final_answer(kind, text, evidence_ids, options?, proposal_id?)`.

## Alternatives considered

- Image editing (Gemini image, diffusion inpainting): invents geometry, no true areas, cannot be checked; prior-art
  guides say not to trust its dimensions (ac-prior §1).
- The model writes coordinates or edit polygons: unverifiable and the main way to hallucinate places; ids only.
- Stateless chat (browser sends history): breaks Gemini's thought signatures and lets the client forge tool results.
- Streaming steps (SSE) tonight: one JSON response per turn is enough (a turn is 1-15 s); the step objects are the
  same if we stream later.
- Swiss reader emits walls: changes extraction counts before QA; `walls_drawn` in `get_plan_geometry` instead (#222).

## Consequences

- Plan edits work only where a page has room polygons and drawn walls (swiss-style vector PDFs today; IFC sheets
  later). Raster scans and photos: the agent says it cannot edit them and why.
- Every Gemini call of the chat charges the spend guard; a turn costs about $0.03-0.08 at Flash prices.
- New: `app/core/agent/`, `app/core/plan_edit/`, `app/adapters/{llm_chat,chat_rules,plan_tools,agent_tools,chat_store}.py`,
  `app/api/chat.py`, settings `CHAT_MODEL`, `AGENT_MODEL`, `AGENT_BASE_URL`, `AGENT_PRICE_IN_PER_M`,
  `AGENT_PRICE_OUT_PER_M`, `AGENT_TURN_USD`; frontend `src/agent/`; OpenAPI + `schema.d.ts`.
- Revisit if the model ignores `final_answer` often (then a forced final step), or if users need to draw polygons
  rather than rectangles.
