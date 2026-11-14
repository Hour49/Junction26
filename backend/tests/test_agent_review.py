""" "Are you sure?" (phase 2 item 3): the agent reviews the chat's latest answer from what the
pipeline already says about it (its level, the check's reason, the marks the readers dispute),
not by repeating the number. Earlier turns' tool results reach the model cut to 1,000
characters, so `review_answer` gives them back whole."""

import json
from typing import Any

import pytest
from test_agent_loop import DRAWING, Model, Tools, call, final, step
from test_agent_view import DOORS, again

from app.adapters.chat_rules import RulesChatModel
from app.core.agent.loop import run_turn
from app.core.agent.model import Caps, Chat
from app.core.spend import SpendGuard

Json = dict[str, Any]

LEVELLED: dict[str, Any] = json.loads(json.dumps(DOORS))
LEVELLED["parts"][0]["answer"]["level"] = {
    "level": "low", "basis": "page", "text": "Low confidence: the page is a scan."}  # fmt: skip


def counted(chat: Chat, tools: Tools) -> None:
    again(chat, Model(step(call("ask_drawings", question="how many doors")),
                      final(text="There are 3 doors [ev_1].", evidence_ids=["ev_1"])),
          tools, "How many doors?")  # fmt: skip


def test_review_answer_gives_the_latest_answer_back_whole_with_its_disputed_marks() -> None:
    chat, tools = Chat("c3f9a1b2c4d5"), Tools(ask_drawings=LEVELLED)
    counted(chat, tools)
    model = Model(
        step(call("review_answer")),
        final(
            text="Not for certain: it is Low and 1 of the 3 doors is disputed [ev_4].",
            evidence_ids=["ev_4"],
        ),
    )
    got = again(chat, model, tools, "Are you sure?")
    assert [name for name, _ in tools.ran] == ["ask_drawings"]  # no new pipeline call
    review = json.loads(model.sent[1][-1]["content"])
    [drawing] = review["drawings"]
    assert (drawing["drawing"], drawing["answer"], drawing["level"]) == ("Drawn plan 1", 3, "low")
    assert drawing["level_text"] == "Low confidence: the page is a scan."
    assert drawing["check"] == "the readers disagree on one door"
    assert drawing["disputed"] == [{"ev": "ev_4", "why": "one reader saw no door"}]
    assert drawing["disputed_count"] == 1
    assert got.kind == "answer" and got.text.endswith("disputed [1].")  # passed the first time
    assert [e.id for e in got.evidence] == ["ev_4"] and len(got.answers) == 1
    [reviewed] = got.steps
    assert (reviewed.tool, reviewed.label, reviewed.status) == (
        "review_answer", "Reviewed the last answer", "ok")  # fmt: skip


def test_review_answer_without_an_earlier_answer_says_so() -> None:
    model = Model(step(call("review_answer")), final(kind="dont_know", text="Nothing to check."))
    got = again(Chat("c3f9a1b2c4d5"), model, Tools(), "Are you sure?")
    assert got.steps[0].status == "error"
    assert "no answer" in json.loads(model.sent[1][-1]["content"])["reason"]


def test_the_rules_planner_answers_are_you_sure_from_the_review() -> None:
    chat, tools = Chat("c3f9a1b2c4d5"), Tools(ask_drawings=LEVELLED)
    rules = RulesChatModel()
    run_turn(chat, "How many doors are there?", (), rules, tools, Caps(), SpendGuard())
    got = run_turn(chat, "Are you sure?", (), rules, tools, Caps(), SpendGuard())
    assert [s.tool for s in got.steps] == ["review_answer"]
    assert got.kind == "answer"
    assert "Low confidence: the page is a scan." in got.text and "disputed" in got.text
    assert [e.id for e in got.evidence] == ["ev_4"]
    assert got.view is not None and [m.box for m in got.view.marks] == [(0.02, 0.5, 0.03, 0.52)]


def test_the_rules_planner_with_nothing_to_review_does_not_know() -> None:
    got = run_turn(Chat("c3f9a1b2c4d5"), "Are you sure?", (), RulesChatModel(), Tools(), Caps(),
                   SpendGuard())  # fmt: skip
    assert got.kind == "dont_know"


@pytest.mark.parametrize(
    ("message", "tool"),
    [
        ("Is the kitchen really the largest room", "ask_drawings"),
        ("How many doors are there in a certain flat?", "ask_drawings"),
        ("Are you sure?", "review_answer"),
        ("really?", "review_answer"),
        ("Can you double-check that", "review_answer"),
    ],
)
def test_only_a_doubt_about_the_answer_is_reviewed(message: str, tool: str) -> None:
    offered = [{"type": "function", "function": {"name": n}}
               for n in ("ask_drawings", "review_answer", "final_answer")]  # fmt: skip
    history = [{"role": "system", "content": "..."}, {"role": "user", "content": message}]
    reply = RulesChatModel().complete(history, offered)
    assert reply.message["tool_calls"][0]["function"]["name"] == tool


def levelled(level: str, disputed: bool = True, question: str = "how many doors") -> Json:
    found: Json = json.loads(json.dumps(DOORS))
    found["question"] = question
    answer = found["parts"][0]["answer"]
    answer["level"] = {"level": level, "basis": "page", "text": f"{level.title()} confidence."}
    if not disputed:
        answer["check"] = {"reason": "the readers agree", "disputed": []}
    return found


def sure(found: Json) -> Any:
    chat, tools, rules = Chat("c3f9a1b2c4d5"), Tools(ask_drawings=found), RulesChatModel()
    run_turn(chat, "How many doors are there?", (), rules, tools, Caps(), SpendGuard())
    return run_turn(chat, "Are you sure?", (), rules, tools, Caps(), SpendGuard())


def test_review_339_s1_a_high_answer_nothing_disputed_is_not_called_uncertain() -> None:
    got = sure(levelled("high", disputed=False))
    assert got.kind == "answer"
    assert got.text == (
        'About "how many doors": Yes, as far as the checks go. plan.pdf: 3. High confidence.'
        " No other reader disputes its marks."
    )


def test_review_339_s1_n1_a_disputed_answer_is_not_for_certain_in_plain_grammar() -> None:
    got = sure(levelled("high"))
    assert "Not for certain." in got.text and "Yes" not in got.text
    assert "1 of its marks is disputed by the other readers: [1]" in got.text


def test_review_339_n1_every_drawing_is_named_with_its_level() -> None:
    two: Json = levelled("high", disputed=False)
    other = json.loads(json.dumps(two["parts"][0]))
    other["drawing_id"], other["name"] = "fedcba9876543210", "other.pdf"
    other["answer"]["level"] = {"level": "low", "basis": "page", "text": "Low confidence."}
    two["parts"].append(other)
    got = sure(two)
    assert got.text.startswith('About "how many doors": Not for certain.')
    assert "plan.pdf: 3. High confidence. No other" in got.text
    assert "other.pdf: 3. Low confidence. No other" in got.text


def test_review_339_n2_a_refused_last_answer_is_called_a_refusal() -> None:
    refused = {"question": "how many doors", "parts": [{"drawing_id": DRAWING, "name": "plan.pdf",
               "answer": {"answer": None, "refusal": {"text": "Nothing was read."}}}]}  # fmt: skip
    got = sure(refused)
    assert (got.kind, got.text) == (
        "dont_know",
        "I can't check that: the last answer was a refusal.",
    )
