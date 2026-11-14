"""`ChatTurn.next` (phase 2 item 7, .agents/chat/contract.md F): follow-up chips the server builds
from the turn's tool results, never from the model's text, and that both planners can answer."""

import json
from typing import Any

from test_agent_loop import Model, Tools, call, final, step, turn
from test_agent_view import DOORS, NAMES, again

from app.adapters.chat_rules import RulesChatModel
from app.core.agent.loop import SHOW_THEM, run_turn
from app.core.agent.model import Caps, Chat
from app.core.spend import SpendGuard

Json = dict[str, Any]
SURE: Json = json.loads(json.dumps(DOORS))  # High, nothing disputed
SURE["parts"][0]["answer"]["level"] = {"level": "high", "basis": "vector", "text": "High."}
SURE["parts"][0]["answer"]["check"] = {"reason": "the readers agree", "disputed": []}


def labels(got: Any) -> list[str]:
    return [chip.label for chip in got.next]


def test_an_answer_showing_some_of_its_disputed_marks_offers_the_rest_and_a_doubt() -> None:
    model = Model(step(call("ask_drawings", question="how many doors")),
                  final(text="There are 3 doors [ev_1].", evidence_ids=["ev_1"]))  # fmt: skip
    got = turn(model, Tools(ask_drawings=DOORS), names=NAMES)
    assert labels(got) == ["Show them on the plan", "Are you sure?"]
    assert [chip.message for chip in got.next] == [SHOW_THEM, "Are you sure?"]


def test_a_sure_answer_with_every_mark_shown_has_no_chips() -> None:
    model = Model(step(call("ask_drawings", question="how many doors")),
                  final(text="3 doors [ev_1][ev_2][ev_3].", evidence_ids=["ev_1"]))  # fmt: skip
    assert turn(model, Tools(ask_drawings=SURE), names=NAMES).next == ()


def test_chips_never_come_with_options_or_on_other_kinds() -> None:
    options = [{"label": "A", "message": "a"}, {"label": "B", "message": "b"}]
    model = Model(step(call("ask_drawings", question="how many doors")),
                  final(kind="needs_input", text="Which?", options=options))  # fmt: skip
    assert turn(model, Tools(ask_drawings=DOORS), names=NAMES).next == ()
    model = Model(step(call("ask_drawings", question="how many doors")),
                  final(kind="dont_know", text="No."))  # fmt: skip
    assert turn(model, Tools(ask_drawings=DOORS), names=NAMES).next == ()


def test_no_are_you_sure_chip_after_a_review() -> None:
    chat, tools = Chat("c3f9a1b2c4d5"), Tools(ask_drawings=DOORS)
    again(chat, Model(step(call("ask_drawings", question="how many doors")),
                      final(text="3 doors [ev_1].", evidence_ids=["ev_1"])), tools)  # fmt: skip
    got = again(chat, Model(final(text="Not for certain [ev_4].", evidence_ids=["ev_4"])),
                tools, "Are you sure?")  # fmt: skip
    assert "Are you sure?" not in labels(got)


def test_a_printed_room_named_without_its_area_offers_its_size() -> None:
    room = {"room": "r1", "label": "OPEN OFFICE 102", "drawing_id": "0123456789abcdef",
            "name": "plan.png", "page": 1, "box": [0.1, 0.1, 0.2, 0.2]}  # fmt: skip
    model = Model(
        step(call("find_rooms", query="office")),
        final(text="OPEN OFFICE 102 is printed here [ev_1].", evidence_ids=["ev_1"]),
    )
    got = turn(model, Tools(find_rooms={"status": "ok", "count": 1, "rooms": [room]}))
    assert [(c.label, c.message) for c in got.next] == [
        ("How big is OPEN OFFICE 102?", "How big is OPEN OFFICE 102?")]  # fmt: skip


def test_every_chip_is_one_the_rules_planner_answers() -> None:
    chat, tools, rules = Chat("c3f9a1b2c4d5"), Tools(ask_drawings=DOORS), RulesChatModel()
    first = run_turn(chat, "How many doors are there?", (), rules, tools, Caps(), SpendGuard())
    assert labels(first) == ["Show them on the plan", "Are you sure?"]
    shown = run_turn(chat, first.next[0].message, (), rules, tools, Caps(), SpendGuard())
    assert [s.tool for s in shown.steps] == ["show_on_plan"] and shown.kind == "answer"
    assert shown.view is not None and len(shown.view.marks) == 3
    assert len(shown.answers) == 1  # the card comes back with them
    sure = run_turn(chat, first.next[1].message, (), rules, tools, Caps(), SpendGuard())
    assert [s.tool for s in sure.steps] == ["review_answer"] and sure.kind == "answer"
    assert [name for name, _ in tools.ran] == ["ask_drawings"]  # neither asked again
