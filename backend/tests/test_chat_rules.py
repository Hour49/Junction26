"""The no-keys planner (spec AC-11) on scripted tool results: its next call from the turn so far."""

import json
from typing import Any

from app.adapters.chat_rules import LOAD, RulesChatModel
from app.core.agent.loop import NUDGE, UNBACKED

DRAWING = "0123456789abcdef"
TOOLS = [{"type": "function", "function": {"name": n}}
         for n in ("list_drawings", "ask_drawings", "list_walls", "propose_remove_wall",
                   "propose_room", "final_answer")]  # fmt: skip
WALLS = {
    "status": "ok", "drawing_id": DRAWING, "page": 1,
    "walls": [
        {"id": "W1", "ev": "ev_1",
         "rooms": [{"id": "r1", "label": "Bagno 1.01"}, {"id": "r2", "label": "Stanza 1.02"}]},
        {"id": "W2", "ev": "ev_2",
         "rooms": [{"id": "r1", "label": "Bagno 1.01"}, {"id": "r3", "label": "Bagno 1.03"}]},
    ],
    "rooms": [{"id": "r1", "label": "Bagno 1.01", "type": "bathroom"},
              {"id": "r2", "label": "Stanza 1.02", "type": "bedroom"},
              {"id": "r3", "label": "Bagno 1.03", "type": "bathroom"}],
}  # fmt: skip


def history(message: str, *done: tuple[str, dict[str, Any], Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = [{"role": "system", "content": "..."},
                                 {"role": "user", "content": message}]  # fmt: skip
    for n, (name, args, result) in enumerate(done):
        call = {"id": f"c{n}", "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)}}  # fmt: skip
        out.append({"role": "assistant", "tool_calls": [call]})
        out.append({"role": "tool", "tool_call_id": f"c{n}", "content": json.dumps(result)})
    return out


def plan(message: str, *done: tuple[str, dict[str, Any], Any]) -> tuple[str, dict[str, Any]]:
    reply = RulesChatModel().complete(history(message, *done), TOOLS)
    assert reply.usd == 0
    [call] = reply.message["tool_calls"]
    return call["function"]["name"], json.loads(call["function"]["arguments"])


def test_ac11_a_question_asks_the_drawings_then_answers_from_them() -> None:
    assert plan("How many doors?") == ("ask_drawings", {"question": "How many doors?"})
    asked = {"parts": [{"drawing_id": DRAWING, "name": "a.pdf", "answer": {
        "answer": 2, "unit": "count", "quantity": {"noun": "doors"},
        "marks": [{"ev": "ev_1"}, {"ev": "ev_2"}]}}]}  # fmt: skip
    name, args = plan("How many doors?", ("ask_drawings", {}, asked))
    assert name == "final_answer"
    assert args == {"kind": "answer", "text": "The drawing answers this below [ev_1].",
                    "evidence_ids": ["ev_1"]}  # fmt: skip
    model = {"drawing_id": DRAWING, "name": "b.ifc", "answer": {"answer": 2, "marks": []}}
    asked["parts"].append(model)
    _, args = plan("How many doors?", ("ask_drawings", {}, asked))
    assert args["text"] == "The drawings answer this below [ev_1]."


def test_ac11_all_refused_is_dont_know_with_the_reason() -> None:
    asked = {"parts": [{"drawing_id": DRAWING, "name": "a.pdf",
                        "answer": {"answer": None, "refusal": {"text": "No scale."}}}]}  # fmt: skip
    _, args = plan("How big?", ("ask_drawings", {}, asked))
    assert (args["kind"], args["text"]) == ("dont_know", "I don't know: no scale.")
    assert "options" not in args


def test_generic_suggestions_are_not_options_for_another_refusal() -> None:
    can = [{"quantity": "door", "label": "door count", "question": "How many doors are there?"}]
    refusal = {"code": "not-in-drawing", "can_answer": can, "text": "No fire rating is drawn."}
    asked = {"parts": [{"drawing_id": DRAWING, "name": "a.pdf",
                        "answer": {"answer": None, "refusal": refusal}}]}  # fmt: skip
    _, args = plan("What is the fire rating?", ("ask_drawings", {}, asked))
    assert args["kind"] == "dont_know" and "options" not in args


def test_ac11_several_rooms_of_the_type_asked_about_ask_which() -> None:
    rooms = [
        {
            "quantity": f"area:room|name={n}",
            "label": f"area of room (name {n})",
            "question": f"What is the net floor area of room {n}?",
        }
        for n in ("1.01", "1.09")
    ]
    refusal = {
        "code": "not-in-drawing",
        "can_answer": rooms,
        "text": "2 rooms on this drawing are of the type bathroom. Ask about one of them.",
    }
    asked = {"parts": [{"drawing_id": DRAWING, "name": "a.pdf",
                        "answer": {"answer": None, "refusal": refusal}}]}  # fmt: skip
    _, args = plan("How big is the bathroom?", ("ask_drawings", {}, asked))
    assert (args["kind"], args["text"]) == ("needs_input", refusal["text"])
    assert args["options"] == [
        {"label": "Room 1.01", "message": "What is the net floor area of room 1.01?"},
        {"label": "Room 1.09", "message": "What is the net floor area of room 1.09?"},
    ]


def test_ac11_a_refusal_carries_its_suggestions_as_options() -> None:
    can = [{"quantity": "door", "label": "door count", "question": "How many doors are there?"}]
    refusal = {
        "code": "unsupported-question",
        "can_answer": can * 5,
        "text": "This question isn't one I can turn into a count. Try one of these instead.",
    }
    asked = {"parts": [{"drawing_id": DRAWING, "name": "a.pdf",
                        "answer": {"answer": None, "refusal": refusal}}]}  # fmt: skip
    _, args = plan("How many parking spaces are there?", ("ask_drawings", {}, asked))
    assert args["kind"] == "dont_know" and args["text"].startswith("I don't know: this question")
    assert args["options"] == [{"label": "door count", "message": "How many doors are there?"}] * 4


def test_ac11_load_bearing_is_dont_know() -> None:
    assert plan("Is that wall load-bearing?")[1]["text"] == LOAD


def test_ac11_remove_a_wall_between_two_named_rooms() -> None:
    message = "Remove the wall between the bathroom and the bedroom"
    assert plan(message)[0] == "list_drawings"
    drawings = ("list_drawings", {}, [{"drawing_id": DRAWING}])
    assert plan(message, drawings) == ("list_walls", {"drawing_id": DRAWING, "page": 1})
    walls = ("list_walls", {"drawing_id": DRAWING, "page": 1}, WALLS)
    proposed = ("propose_remove_wall", {"drawing_id": DRAWING, "page": 1, "wall_id": "W1"})
    assert plan(message, drawings, walls) == proposed
    proposal = {"status": "ok", "proposal": {
        "proposal_id": "p1", "removed": [{"label": "Wall W1"}], "unknowns": ["Load: unknown."],
        "rooms": [{"label": "Bagno 1.01 + Stanza 1.02", "area_before_m2": 20.66,
                   "area_after_m2": 21.0}]}}  # fmt: skip
    name, args = plan(message, drawings, walls, (*proposed, proposal))
    assert name == "final_answer" and args["kind"] == "edit" and args["proposal_id"] == "p1"
    assert args["evidence_ids"] == ["ev_1"] and "20.66 → 21.0 m²" in args["text"]


def test_ac11_rooms_named_by_label_or_number() -> None:
    drawings = ("list_drawings", {}, [{"drawing_id": DRAWING}])
    walls = ("list_walls", {"drawing_id": DRAWING, "page": 1}, WALLS)
    for message in ("Remove the wall between Bagno 1.01 and Stanza 1.02",
                    "Remove the wall between 1.01 and 1.02", "Knock down the wall to the Stanza",
                    "Remove the wall between Bagno 1.01 and Bagno 1.03"):  # fmt: skip
        name, args = plan(message, drawings, walls)
        assert name == "propose_remove_wall", (message, args)
        assert args["wall_id"] == ("W2" if "1.03" in message else "W1")


def test_ac11_several_matching_walls_ask_which() -> None:
    drawings = ("list_drawings", {}, [{"drawing_id": DRAWING}])
    walls = ("list_walls", {"drawing_id": DRAWING, "page": 1}, WALLS)
    name, args = plan("Make the bathroom larger", drawings, walls)
    assert name == "final_answer" and args["kind"] == "needs_input"
    assert [o["message"] for o in args["options"]] == [
        "Remove wall W1 between Bagno 1.01 and Stanza 1.02",
        "Remove wall W2 between Bagno 1.01 and Bagno 1.03",
    ]
    assert plan("Remove wall W2 between Bagno 1.01 and Bagno 1.03", drawings, walls)[1][
        "wall_id"] == "W2"  # fmt: skip


def test_ac11_a_scan_cannot_be_edited() -> None:
    drawings = ("list_drawings", {}, [{"drawing_id": DRAWING}])
    scan = {"status": "cannot_edit", "reason": "this plan is a scan: its walls are not geometry"}
    walls = ("list_walls", {"drawing_id": DRAWING, "page": 1}, scan)
    _, args = plan("Remove the wall", drawings, walls)
    assert args["kind"] == "dont_know"
    assert (
        args["text"] == "I can't edit this plan: this plan is a scan: its walls are not geometry."
    )


def test_ac11_a_region_and_a_room_proposes_a_room() -> None:
    message = "Put a storage room here\nsel_1: region on a.pdf page 1, about 2 x 1 m"
    assert plan(message) == ("propose_room", {"selection_id": "sel_1", "name": "Storage"})


def test_a_refused_final_answer_ends_in_dont_know() -> None:
    refused = ("final_answer", {"kind": "answer", "text": "9"}, {"error": "numbers"})
    assert plan("How many doors?", refused)[1] == {"kind": "dont_know", "text": UNBACKED,
                                                  "evidence_ids": []}  # fmt: skip


def test_the_nudge_is_not_the_users_message() -> None:
    messages = [*history("How many doors?"), {"role": "user", "content": NUDGE}]
    reply = RulesChatModel().complete(messages, TOOLS)
    assert reply.message["tool_calls"][0]["function"]["name"] == "ask_drawings"
