"""The chat asks about an open issue before it answers (decision 0018): the matching, the ask
turn, and the cap, with a scripted model."""

import copy
from typing import Any

from test_agent_loop import ASKED, DRAWING, Model, Tools, call, final, step, turn

from app.core.agent.issue_ask import SKIP, Asker, options_of, related
from app.core.agent.model import Chat

Json = dict[str, Any]
KEY = "area:room|name=1.01"
CONFLICTED: Json = copy.deepcopy(ASKED)
CONFLICTED["parts"][0]["answer"]["quantity"] = {
    "key": KEY, "unit": "m2", "status": "conflict",
    "conflict": {"values": [{"value": 22.401, "method": "polygon_x_scale"},
                            {"value": 30.0, "method": "printed_label"}]},
}  # fmt: skip
CONFLICT: Json = {
    "id": "conflict-1", "kind": "conflict", "severity": "needs_person", "state": "open",
    "drawing_id": DRAWING, "drawing_name": "Drawn plan 1", "file": "plan.pdf", "quantity": KEY,
    "question": None, "label": "Area of room (name Bagno · 1.01)",
    "why": "Area of room 1.01: checked twice, they disagree.",
    "suggestions": ["Check it on site"], "answer": None,
}  # fmt: skip


def issue(**more: Any) -> Json:
    return {**CONFLICT, **more}


def test_a_needs_person_conflict_on_the_asked_quantity_is_related() -> None:
    assert related([issue()], CONFLICTED, frozenset()) == [issue()]
    # the storey's row is the sheet's row (K4)
    assert related([issue(quantity=f"{KEY}|storey=p1")], CONFLICTED, frozenset())


def test_what_is_not_asked() -> None:
    nothing = frozenset[str]()
    assert not related([issue(severity="note")], CONFLICTED, nothing)  # a rule decides it
    assert not related([issue(state="settled")], CONFLICTED, nothing)
    assert not related([issue(answer={"text": "ok", "by": "Ana", "at": "t"})], CONFLICTED, nothing)
    assert not related([issue()], CONFLICTED, frozenset({"conflict-1"}))  # skipped (D2)
    assert not related([issue(quantity="door")], CONFLICTED, nothing)
    assert not related([issue(drawing_id="other")], CONFLICTED, nothing)
    assert not related([issue(kind="set_aside", severity="note")], CONFLICTED, nothing)


def test_a_reading_flag_only_on_a_drawing_that_answered() -> None:
    flag = issue(kind="reading_flag", severity="note", quantity=None)
    assert related([flag], ASKED, frozenset())
    refused: Json = copy.deepcopy(ASKED)
    refused["parts"][0]["answer"] = {"answer": None, "refusal": {"code": "no-reader"}}
    assert not related([flag], refused, frozenset())


def test_a_refusal_is_a_note_and_is_not_asked() -> None:
    refusal = issue(kind="refused_answer", severity="note", question="How big is the Bathroom?")
    assert not related([refusal], ASKED, frozenset())


def test_a_conflicts_choices_are_its_values_then_suggestions_then_skip() -> None:
    options = options_of(issue(), CONFLICTED)
    assert [(o.label, o.value, o.skip) for o in options] == [
        ("Use 22.4 m² (room outlines)", 22.401, None),
        ("Use 30 m² (printed areas)", 30.0, None),
        ("Check it on site", None, None),
        (SKIP, None, True),
    ]


def test_the_turn_asks_before_the_model_answers_and_holds_the_question() -> None:
    model = Model(step(call("ask_drawings", question="how big is the bathroom")))
    chat = Chat("c3f9a1b2c4d5")
    got = turn(model, Tools(ask_drawings=CONFLICTED), chat, message="How big is the bathroom?",
               ask=Asker(load=lambda: [issue()]))  # fmt: skip
    assert got.kind == "ask_issue" and got.issue == issue() and got.answers == ()
    assert got.text.startswith("Before I answer: Drawn plan 1 has an open issue on this.")
    assert got.options and got.options[-1].skip
    assert len(model.sent) == 1  # no final_answer was asked of the model
    assert chat.pending == {
        "question": "How big is the bathroom?",
        "issue": issue(),
        "asks": 1,
        "values": [22.401, 30.0],  # what a reply may settle to (R4)
    }
    # the next turn, with the person's answer, answers it and clears the hold
    model = Model(
        step(call("ask_drawings", question="how big is the bathroom")),
        final(text="It is 7.56 m² [ev_2].", evidence_ids=["ev_2"]),
    )
    settled = issue(state="settled")
    after = turn(model, Tools(ask_drawings=ASKED), chat, message="How big is the bathroom?",
                 ask=Asker(load=lambda: [settled], left=1))  # fmt: skip
    assert after.kind == "answer" and chat.pending is None


def test_no_asks_left_answers_with_the_ending() -> None:
    model = Model(
        step(call("ask_drawings", question="q")),
        final(kind="conflict", text="The sources disagree [ev_1].", evidence_ids=["ev_1"]),
    )
    got = turn(model, Tools(ask_drawings=CONFLICTED), ask=Asker(load=lambda: [issue()], left=0),
               ending="Do you have other questions?")  # fmt: skip
    assert got.kind == "conflict" and got.text.endswith(" Do you have other questions?")


def test_d5_an_answered_issue_is_told_to_the_model_not_asked() -> None:
    noted = issue(answer={"text": "Check it on site", "by": "Ana", "at": "t"})
    model = Model(
        step(call("ask_drawings", question="q")),
        final(kind="conflict", text="The sources disagree [ev_1].", evidence_ids=["ev_1"]),
    )
    got = turn(model, Tools(ask_drawings=CONFLICTED), ask=Asker(load=lambda: [noted]))
    assert got.kind == "conflict"
    assert '"people_answered"' in model.sent[1][-1]["content"]
    assert "Check it on site" in model.sent[1][-1]["content"]
