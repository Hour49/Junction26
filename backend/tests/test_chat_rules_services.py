"""SV-26: the no-keys planner's services rules on scripted tool results (spec services-model.md):
a move of a radiator, socket or air terminal goes list_services -> propose_move_terminal; "what
feeds", "what does ... serve", "what is cut off" go to ask_services."""

import json
from typing import Any

from app.adapters.chat_rules import RulesChatModel

IFC, PDF = "0123456789abcdef", "fedcba9876543210"
TOOLS = [{"type": "function", "function": {"name": n}}
         for n in ("list_drawings", "ask_drawings", "list_walls", "propose_remove_wall",
                   "propose_room", "list_services", "ask_services", "propose_move_terminal",
                   "final_answer")]  # fmt: skip
DRAWINGS = [{"drawing_id": PDF, "name": "plan.pdf", "kind": "pdf"},
            {"drawing_id": IFC, "name": "m/heating.ifc", "kind": "ifc"}]  # fmt: skip
E2 = {"id": "E2", "kind": "space_heater", "label": "Radiator 22-600", "room": "SR1", "ev": "ev_1"}
E3 = {**E2, "id": "E3", "room": "SR2", "ev": "ev_2"}
LISTED = {"drawing_id": IFC, "items": [E2], "more": 0}
WALLS = {"drawing_id": IFC, "room": {"id": "SR1", "name": "Room 1"}, "items": [E2],
         "walls": [{"id": "SW1", "free_m": 4.0, "mounted": ["E2"]},
                   {"id": "SW3", "free_m": 4.0, "mounted": []},
                   {"id": "SW2", "free_m": 5.0, "mounted": []}]}  # fmt: skip
PROPOSED = {"status": "ok", "proposal": {
    "proposal_id": "p1", "drawing_id": IFC, "page": 1, "op": "move_terminal",
    "moved": [{"id": "E2", "label": "Radiator 22-600", "from": [0.2, 0.9], "to": [0.2, 0.1]}],
    "facts": [{"what": "pipe length", "system": "Heating Supply", "size": "DN15", "unit": "m",
               "before": 10.5, "after": 14.25}],
    "checks": [{"code": "connected", "ok": True, "text": "The heating network is in one piece."},
               {"code": "reach", "ok": False, "text": "E9 no longer reaches the boiler."}],
    "unknowns": ["Whether the new run clashes with other services: not checked."]}}  # fmt: skip
Done = tuple[str, dict[str, Any], Any]


def history(message: str, *done: Done) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = [{"role": "system", "content": "..."},
                                 {"role": "user", "content": message}]  # fmt: skip
    for n, (name, args, result) in enumerate(done):
        call = {"id": f"c{n}", "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)}}  # fmt: skip
        out.append({"role": "assistant", "tool_calls": [call]})
        out.append({"role": "tool", "tool_call_id": f"c{n}", "content": json.dumps(result)})
    return out


def plan(message: str, *done: Done, tools: list[Any] = TOOLS) -> tuple[str, dict[str, Any]]:
    reply = RulesChatModel().complete(history(message, *done), tools)
    [call] = reply.message["tool_calls"]
    return call["function"]["name"], json.loads(call["function"]["arguments"])


LISTING: Done = ("list_drawings", {}, DRAWINGS)
FOUND: Done = ("list_services", {"drawing_id": IFC, "kind": "space_heater"}, LISTED)
ROOM: Done = ("list_services", {"drawing_id": IFC, "room_id": "SR1"}, WALLS)


def test_sv26_move_a_radiator_lists_then_proposes_on_the_freest_other_wall() -> None:
    message = "Move the radiator to another wall"
    assert plan(message) == ("list_drawings", {})
    # the IFC drawing first: it is the one with a services model
    assert plan(message, LISTING) == ("list_services", {"drawing_id": IFC, "kind": "space_heater"})
    assert plan(message, LISTING, FOUND) == ("list_services", {"drawing_id": IFC, "room_id": "SR1"})
    move = {"drawing_id": IFC, "element_id": "E2", "wall_id": "SW2"}
    assert plan(message, LISTING, FOUND, ROOM) == ("propose_move_terminal", move)
    name, args = plan(message, LISTING, FOUND, ROOM, ("propose_move_terminal", move, PROPOSED))
    assert name == "final_answer" and args["kind"] == "edit" and args["proposal_id"] == "p1"
    text = args["text"]
    assert "Radiator 22-600" in text and "SW2" in text and "10.5 → 14.25 m" in text
    assert "E9 no longer reaches the boiler." in text  # a failed check is said
    assert "in one piece" not in text and args["evidence_ids"] == ["ev_1"]


def test_sv26_a_refused_wall_tries_the_next_one_then_says_why() -> None:
    message = "relocate the heater"
    refused = {"status": "refused", "reason": "There is no room on that wall."}
    first = {"drawing_id": IFC, "element_id": "E2", "wall_id": "SW2"}
    second = {**first, "wall_id": "SW3"}
    tried: list[Done] = [LISTING, FOUND, ROOM, ("propose_move_terminal", first, refused)]
    assert plan(message, *tried) == ("propose_move_terminal", second)
    name, args = plan(message, *tried, ("propose_move_terminal", second, refused))
    assert (name, args["kind"]) == ("final_answer", "dont_know")
    assert "There is no room on that wall." in args["text"]


def test_sv26_the_ids_the_message_names_win() -> None:
    message = "move radiator E2 to wall SW3"
    move = {"drawing_id": IFC, "element_id": "E2", "wall_id": "SW3"}
    assert plan(message, LISTING, FOUND) == ("propose_move_terminal", move)


def test_sv26_several_radiators_ask_which_and_the_answer_names_it() -> None:
    several = {**LISTED, "items": [E2, E3]}
    found: Done = ("list_services", {"drawing_id": IFC, "kind": "space_heater"}, several)
    name, args = plan("move the radiator", LISTING, found)
    assert (name, args["kind"]) == ("final_answer", "needs_input")
    assert [o["message"] for o in args["options"]] == ["Move radiator E2", "Move radiator E3"]
    assert args["evidence_ids"] == ["ev_1", "ev_2"]
    assert plan("Move radiator E3", LISTING, found) == (
        "list_services", {"drawing_id": IFC, "room_id": "SR2"})  # fmt: skip


def test_sv26_a_selection_on_the_services_picture_narrows_the_list() -> None:
    message = "move the radiator in this room\nsel_1: region on m/heating.ifc page 1, no room"
    narrowed = {"drawing_id": IFC, "kind": "space_heater", "selection_id": "sel_1"}
    assert plan(message, LISTING) == ("list_services", narrowed)


def test_sv26_sockets_and_air_terminals_by_their_kind() -> None:
    assert plan("shift the socket", LISTING)[1]["kind"] == "outlet"
    assert plan("move this diffuser", LISTING)[1]["kind"] == "air_terminal"
    assert plan("move the air terminal", LISTING)[1]["kind"] == "air_terminal"


def test_sv26_no_services_model_says_so() -> None:
    error = {"error": "drawing 'x' has no services model; the project's services models: none"}
    done = [LISTING, ("list_services", {"drawing_id": IFC}, error),
            ("list_services", {"drawing_id": PDF}, error)]  # fmt: skip
    name, args = plan("move the radiator", *done)
    assert (name, args["kind"]) == ("final_answer", "dont_know")
    assert "no services model" in args["text"]


def test_sv26_what_feeds_asks_the_network() -> None:
    message = "What feeds radiator E2?"
    listed: Done = ("list_services", {"drawing_id": IFC, "kind": "space_heater"}, LISTED)
    assert plan(message, LISTING) == ("list_services", {"drawing_id": IFC, "kind": "space_heater"})
    ask = {"drawing_id": IFC, "op": "feeds", "element_id": "E2"}
    assert plan(message, LISTING, listed) == ("ask_services", ask)
    fed = {"drawing_id": IFC, "status": "ok", "value": ["E1"],
           "elements": [{"id": "E1", "page": 1, "ev": "ev_3"}]}  # fmt: skip
    name, args = plan(message, LISTING, listed, ("ask_services", ask, fed))
    assert (name, args["kind"]) == ("final_answer", "answer")
    assert args["text"] == "E2 is fed by E1 [ev_3]." and args["evidence_ids"] == ["ev_3"]


def test_sv26_what_does_serve_and_what_is_cut_off() -> None:
    listed: Done = ("list_services", {"drawing_id": IFC}, LISTED)
    message = "what does E1 serve?"
    assert plan(message, LISTING, listed)[1]["op"] == "terminals_served"
    served = {"status": "ok", "value": 2, "elements": [{"id": "E2", "ev": "ev_3"},
                                                       {"id": "E3", "ev": "ev_4"}]}  # fmt: skip
    ask = {"drawing_id": IFC, "op": "terminals_served", "element_id": "E1"}
    _, args = plan(message, LISTING, listed, ("ask_services", ask, served))
    assert args["text"] == "E1 serves 2 terminals: E2 [ev_3], E3 [ev_4]."
    for message in ("What is cut off if E4 closes?", "what does closing E4 cut off"):
        assert plan(message, LISTING, listed)[1]["op"] == "cut_off"
    cut = {"status": "ok", "value": 5, "terminals": 1, "elements": [{"id": "E2", "ev": "ev_3"}]}
    ask = {"drawing_id": IFC, "op": "cut_off", "element_id": "E4"}
    _, args = plan("What is cut off if E4 closes?", LISTING, listed, ("ask_services", ask, cut))
    assert args["text"] == "Closing E4 cuts off 5 elements, 1 of them terminals: E2 [ev_3]."
    unknown = {"status": "unknown", "reason": "the model does not say which way the flow goes"}
    _, args = plan("What is cut off if E4 closes?", LISTING, listed, ("ask_services", ask, unknown))
    assert args["kind"] == "dont_know" and "which way the flow goes" in args["text"]


def test_sv26_a_question_without_an_element_asks_for_one() -> None:
    several = {**LISTED, "items": [E2, E3]}
    listed: Done = ("list_services", {"drawing_id": IFC, "kind": "space_heater"}, several)
    name, args = plan("what feeds the radiator?", LISTING, listed)
    assert (name, args["kind"]) == ("final_answer", "needs_input")
    assert [o["message"] for o in args["options"]] == ["What feeds E2?", "What feeds E3?"]


def test_sv26_without_the_services_tools_the_old_rules_hold() -> None:
    plain = [t for t in TOOLS if not t["function"]["name"].endswith("services")]
    assert plan("move the radiator", tools=plain)[0] == "ask_drawings"
    message = "Put a room here\nsel_1: region on plan.pdf page 1, about 2.0 m by 3.0 m"
    assert plan(message)[0] == "propose_room"  # no services word: the plan rule
