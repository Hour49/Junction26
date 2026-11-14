"""The plan a turn wants on screen (`ChatTurn.view`), `show_on_plan`, and places and answer cards
kept across turns (.agents/chat/contract.md A-B, phase 2 item 1)."""

import json
from typing import Any

from test_agent_loop import DRAWING, PROPOSAL, Model, Tools, call, final, step, turn

from app.core.agent.loop import run_turn
from app.core.agent.model import Caps, Chat
from app.core.spend import SpendGuard

Json = dict[str, Any]
SQUARE = [[0.1, 0.2], [0.2, 0.2], [0.2, 0.3], [0.1, 0.3]]


def door(n: int, page: int = 1) -> Json:
    x = n / 100
    return {"id": f"m{n}", "page": page, "box": [x, 0.5, x + 0.01, 0.52], "label": "door",
            "polygon": [[x, 0.5], [x + 0.01, 0.5], [x + 0.01, 0.52]]}  # fmt: skip


DOORS: Json = {
    "question": "how many doors",
    "parts": [{
        "drawing_id": DRAWING, "name": "plan.pdf",
        "answer": {"answer": 3, "unit": "count", "line": {"sure": False},
                   "marks": [door(1), door(2), door(3)],
                   "check": {"reason": "the readers disagree on one door",
                             "disputed": [{"mark_id": "m2", "page": 1,
                                           "box": [0.02, 0.5, 0.03, 0.52],
                                           "why": "one reader saw no door"}]}},
    }],
}  # fmt: skip
NAMES = {DRAWING: "Drawn plan 1"}


def again(chat: Chat, model: Model, tools: Tools, message: str = "Show me") -> Any:
    return run_turn(chat, message, (), model, tools, Caps(), SpendGuard(), names=NAMES)


def test_an_answer_with_places_moves_the_plan_to_its_first_source() -> None:
    model = Model(
        step(call("ask_drawings", question="how many doors")),
        final(text="There are 3 doors [ev_1], [ev_2].", evidence_ids=["ev_1", "ev_2"]),
    )
    got = turn(model, Tools(ask_drawings=DOORS), names=NAMES)
    assert got.view is not None
    assert (got.view.drawing_id, got.view.name, got.view.page, got.view.source) == (
        DRAWING, "Drawn plan 1", 1, "evidence")  # fmt: skip
    assert [(m.n, m.label) for m in got.view.marks] == [(1, "door"), (2, "door")]
    assert got.view.marks[0].polygon == ((0.01, 0.5), (0.02, 0.5), (0.02, 0.52))
    x0, y0, x1, y1 = got.view.box  # the marks' union with a margin, inside the page
    assert x0 == 0.0 and y0 < 0.5 and x1 > 0.03 and y1 > 0.52 and x1 <= 1.0


def test_a_turn_without_places_has_no_view() -> None:
    got = turn(Model(final(kind="dont_know", text="The drawings do not say.")))
    assert got.view is None


def test_show_on_plan_shows_every_mark_of_the_last_answer_on_a_follow_up() -> None:
    """ "Show me where they are" after a count: the earlier answer's marks, no new pipeline call,
    and its answer card comes back with the turn."""
    chat = Chat("c3f9a1b2c4d5")
    tools = Tools(ask_drawings=DOORS)
    again(chat, Model(step(call("ask_drawings", question="how many doors")),
                      final(text="There are 3 doors [ev_1].", evidence_ids=["ev_1"])),
          tools, "How many doors?")  # fmt: skip
    model = Model(
        step(call("show_on_plan", answer="latest", caption="The 3 doors")),
        final(text="Here they are on the plan."),
    )
    got = again(chat, model, tools, "Show me where they are")
    assert [name for name, _ in tools.ran] == ["ask_drawings"]  # the pipeline ran once
    assert got.view is not None and got.view.source == "show_on_plan"
    assert got.view.caption == "The 3 doors"
    assert len(got.view.marks) == 3 and {m.label for m in got.view.marks} == {"door"}
    assert [e.n for e in got.evidence] == [1, 2, 3]  # every mark has its sources row
    assert [m.n for m in got.view.marks] == [1, 2, 3]
    assert len(got.answers) == 1 and got.answers[0]["question"] == "how many doors"
    [shown] = got.steps
    assert (shown.tool, shown.status, shown.label) == (
        "show_on_plan", "ok", "Showed the 3 doors on the plan")  # fmt: skip


def test_show_on_plan_disputed_shows_the_marks_the_readers_disagree_on() -> None:
    model = Model(
        step(call("ask_drawings", question="how many doors")),
        step(call("show_on_plan", 2, answer="latest", marks="disputed", caption="One door")),
        final(text="One door is disputed."),
    )
    got = turn(model, Tools(ask_drawings=DOORS), names=NAMES)
    assert got.view is not None
    assert [m.box for m in got.view.marks] == [(0.02, 0.5, 0.03, 0.52)]


def test_a_place_from_an_earlier_turn_can_be_cited_again() -> None:
    chat = Chat("c3f9a1b2c4d5")
    tools = Tools(ask_drawings=DOORS)
    again(chat, Model(step(call("ask_drawings", question="how many doors")),
                      final(text="There are 3 doors [ev_1].", evidence_ids=["ev_1"])),
          tools, "How many doors?")  # fmt: skip
    got = again(chat, Model(final(text="The first door is here [ev_2].", evidence_ids=["ev_2"])),
                tools, "Where is the first door?")  # fmt: skip
    assert got.kind == "answer" and got.text == "The first door is here [1]."
    [evidence] = got.evidence
    assert (evidence.id, evidence.label, evidence.name) == ("ev_2", "door", "Drawn plan 1")
    assert len(got.answers) == 1  # the answer card it rests on, from turn 1
    assert got.view is not None and [m.n for m in got.view.marks] == [1]


def test_show_on_plan_refuses_places_on_two_pages() -> None:
    two = {"parts": [{"drawing_id": DRAWING, "name": "plan.pdf",
                      "answer": {"answer": 2, "marks": [door(1), door(2, page=2)]}}]}  # fmt: skip
    model = Model(
        step(call("ask_drawings", question="doors")),
        step(call("show_on_plan", 2, evidence_ids=["ev_1", "ev_2"], caption="Both doors")),
        final(text="There are 2 doors [ev_1].", evidence_ids=["ev_1"]),
    )
    got = turn(model, Tools(ask_drawings=two), names=NAMES)
    shown = got.steps[-1]
    assert (shown.tool, shown.status) == ("show_on_plan", "error")
    assert "one page at a time" in model.sent[2][-1]["content"]
    assert got.view is not None and got.view.source == "evidence"


def test_an_unknown_evidence_id_is_an_error_for_the_model() -> None:
    model = Model(
        step(call("show_on_plan", evidence_ids=["ev_9"], caption="x")),
        final(kind="dont_know", text="Nothing to show."),
    )
    got = turn(model, Tools())
    assert got.steps[-1].status == "error" and "ev_9" in model.sent[1][-1]["content"]
    assert got.view is None


def test_a_caption_with_a_number_no_tool_gave_is_replaced_by_the_server() -> None:
    model = Model(
        step(call("ask_drawings", question="how many doors")),
        step(call("show_on_plan", 2, answer="latest", caption="The 12 doors")),
        final(text="Shown."),
    )
    got = turn(model, Tools(ask_drawings=DOORS), names=NAMES)
    assert got.view is not None and got.view.caption == "3 places on Drawn plan 1, page 1"


def test_an_edit_turn_views_its_page_around_the_proposal() -> None:
    model = Model(
        step(call("propose_remove_wall", wall_id="W4")),
        final(kind="edit", text="Removing wall W4 merges the rooms.", proposal_id="p1"),
    )
    got = turn(model, Tools(propose_remove_wall=PROPOSAL), names=NAMES)
    assert got.view is not None and (got.view.drawing_id, got.view.page) == (DRAWING, 1)
    assert got.view.marks == ()
    x0, y0, x1, y1 = got.view.box  # around the merged room and the wall
    assert x0 < 0.3 and y0 < 0.2 and x1 > 0.5 and y1 > 0.3


def test_places_and_answers_survive_the_chat_file(tmp_path: Any) -> None:
    from app.adapters.chat_store import JsonChatStore

    store = JsonChatStore(tmp_path)
    chat = store.new()
    tools = Tools(ask_drawings=DOORS)
    again(chat, Model(step(call("ask_drawings", question="how many doors")),
                      final(text="There are 3 doors [ev_1].", evidence_ids=["ev_1"])),
          tools, "How many doors?")  # fmt: skip
    store.put("p1", chat)
    kept = store.get("p1", chat.chat_id)
    assert set(kept.evidence) == set(chat.evidence) and kept.asked == json.loads(
        json.dumps(chat.asked))  # fmt: skip
    got = again(kept, Model(step(call("show_on_plan", answer="latest", caption="The 3 doors")),
                            final(text="Here.")), tools)  # fmt: skip
    assert got.view is not None and len(got.view.marks) == 3 and len(got.answers) == 1


def test_a_follow_up_may_state_the_numbers_of_the_answer_it_shows() -> None:
    """Live 2026-11-14: "Show me where they are" → show_on_plan, then "the 3 doors" was refused
    once (the shown answer's numbers did not back the text), a whole model step lost."""
    chat = Chat("c3f9a1b2c4d5")
    tools = Tools(ask_drawings=DOORS)
    again(chat, Model(step(call("ask_drawings", question="how many doors")),
                      final(text="There are 3 doors [ev_1].", evidence_ids=["ev_1"])),
          tools, "How many doors?")  # fmt: skip
    model = Model(
        step(call("show_on_plan", answer="latest", caption="The doors")),
        final(text="Here are the 3 doors on the plan."),
    )
    got = again(chat, model, tools, "Show me where they are")
    assert (got.kind, got.text) == ("answer", "Here are the 3 doors on the plan.")


def test_list_drawings_gives_each_drawing_its_plain_name_as_title() -> None:
    """The user names a sheet as the app shows it ("Drawn plan 1"), not by its file (multi)."""
    listed = [
        {"drawing_id": DRAWING, "name": "plan.pdf"},
        {"drawing_id": "f" * 16, "name": "b.pdf"},
    ]
    model = Model(step(call("list_drawings")), final(kind="dont_know", text="No."))
    turn(model, Tools(list_drawings=listed), names=NAMES)
    seen = json.loads(model.sent[1][-1]["content"])
    assert seen == [{**listed[0], "title": "Drawn plan 1"}, listed[1]]
