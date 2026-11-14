"""What the model reads of a long tool result (loop._for_model): lists stay lists of what they
held, what was cut is a count beside them, and the wall between two named rooms stays reachable
(chat-eval 2026-11-14: a "... N more" string in the walls list made the rules planner 500 on
"Remove the wall between the kitchen and the living room", and hid the wall from Gemini)."""

import json
from typing import Any

from app.adapters.chat_rules import RulesChatModel
from app.core.agent.loop import TOOL_CHARS, _for_model

Json = dict[str, Any]
DRAWING = "0123456789abcdef"
NAMES = ("list_drawings", "list_walls", "propose_remove_wall", "final_answer")
TOOLS = [{"type": "function", "function": {"name": n}} for n in NAMES]
ROOMS = [{"id": "r1", "label": "Kitchen", "type": "kitchen"},
         {"id": "r2", "label": "Living room", "type": "living"}]  # fmt: skip
HALL = [{"id": "r9", "label": "Hall", "type": "corridor"}, {"id": "r8", "label": "Stair"}]
# 200 walls, the one between kitchen and living room last: a cut drops it
WALLS: Json = {
    "status": "ok", "drawing_id": DRAWING, "page": 1, "rooms": ROOMS,
    "walls": [{"id": f"W{n}", "ev": f"ev_{n}", "rooms": HALL} for n in range(1, 200)]
    + [{"id": "W200", "ev": "ev_200", "rooms": [ROOMS[0], ROOMS[1]]}],
}  # fmt: skip
BETWEEN: Json = {**WALLS, "walls": WALLS["walls"][-1:]}  # list_walls(room_a=r1, room_b=r2)


def _types(found: Any) -> set[type]:
    if isinstance(found, list):
        return {type(item) for item in found}  # pyright: ignore[reportUnknownVariableType]
    return set()


def test_a_cut_list_keeps_its_items_typed_and_says_how_many_were_cut() -> None:
    seen = json.loads(_for_model(WALLS))
    assert _types(seen["walls"]) == {dict}
    assert seen["walls_more"] == 200 - len(seen["walls"]) > 0
    assert seen["rooms"] == ROOMS  # the short list is not cut while the long one can be
    assert len(_for_model(WALLS)) <= TOOL_CHARS


def test_a_cut_top_level_list_says_how_many_were_cut() -> None:
    rows = [{"drawing_id": DRAWING, "name": "x" * 200} for _ in range(100)]
    seen = json.loads(_for_model(rows))
    assert _types(seen["items"]) == {dict} and seen["items_more"] == 100 - len(seen["items"])


def test_a_result_that_fits_is_not_cut() -> None:
    assert json.loads(_for_model(BETWEEN)) == BETWEEN


def plan(message: str, *calls: tuple[str, Json, Any]) -> tuple[str, Json]:
    history: list[Json] = [
        {"role": "system", "content": "..."},
        {"role": "user", "content": message},
    ]
    for n, (name, args, result) in enumerate(calls):
        call = {"id": f"c{n}", "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)}}  # fmt: skip
        history.append({"role": "assistant", "tool_calls": [call]})
        history.append({"role": "tool", "tool_call_id": f"c{n}", "content": _for_model(result)})
    function = RulesChatModel().complete(history, TOOLS).message["tool_calls"][0]["function"]
    return function["name"], json.loads(function["arguments"])


MESSAGE = "Remove the wall between the kitchen and the living room"
LISTED = ("list_drawings", {}, [{"drawing_id": DRAWING}])
PAGE = {"drawing_id": DRAWING, "page": 1}


def test_rules_asks_for_the_walls_between_the_named_rooms_when_the_list_was_cut() -> None:
    name, args = plan(MESSAGE, LISTED, ("list_walls", PAGE, WALLS))
    assert (name, args) == ("list_walls", {**PAGE, "room_a": "r1", "room_b": "r2"})


def test_rules_removes_the_wall_the_filtered_list_gives() -> None:
    filtered = ("list_walls", {**PAGE, "room_a": "r1", "room_b": "r2"}, BETWEEN)
    name, args = plan(MESSAGE, LISTED, ("list_walls", PAGE, WALLS), filtered)
    assert (name, args) == ("propose_remove_wall", {**PAGE, "wall_id": "W200"})
