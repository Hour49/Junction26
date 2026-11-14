""" "Are you sure?" (phase 2 item 3): the agent reviews the chat's latest answer from what the
pipeline already says about it (its level, the check's reason, the marks the readers dispute),
not by repeating the number. Earlier turns' tool results reach the model cut to 1,000
characters, so `review_answer` gives them back whole."""

import json
from typing import Any

import pytest
from test_agent_loop import DRAWING, Model, Tools, call, final, step
from test_agent_view import DOORS, NAMES, again

from app.adapters.chat_rules import RulesChatModel
from app.core.agent.loop import run_turn
from app.core.agent.model import Caps, Chat
from app.core.agent.review import DOUBT, REVIEWED
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
    """The model calls it ("why ..." is no doubt the server reviews first)."""
    chat, tools = Chat("c3f9a1b2c4d5"), Tools(ask_drawings=LEVELLED)
    counted(chat, tools)
    model = Model(
        step(call("review_answer")),
        final(
            text="Not for certain: it is Low and 1 of the 3 doors is disputed [ev_4].",
            evidence_ids=["ev_4"],
        ),
    )
    got = again(chat, model, tools, "Why is that low?")
    assert [name for name, _ in tools.ran] == ["ask_drawings"]  # no new pipeline call
    review = json.loads(model.sent[1][-1]["content"])
    [drawing] = review["drawings"]
    assert (drawing["drawing"], drawing["answer"], drawing["level"]) == ("Drawn plan 1", 3, "low")
    assert drawing["level_text"] == "Low confidence: the page is a scan."
    assert drawing["check"] == "the readers disagree on one door"
    assert drawing["disputed"] == [{"ev": "ev_4", "why": "one reader saw no door"}]
    assert drawing["disputed_count"] == 1
    assert (drawing["marks"], drawing["marks_count"]) == (["ev_1", "ev_2", "ev_3"], 3)
    assert got.kind == "answer" and got.text.endswith("disputed [1].")  # passed the first time
    assert [e.id for e in got.evidence] == ["ev_4"] and len(got.answers) == 1
    [reviewed] = got.steps
    assert (reviewed.tool, reviewed.label, reviewed.status) == (
        "review_answer", "Reviewed the last answer", "ok")  # fmt: skip


def test_a_doubt_is_reviewed_before_the_model_so_one_model_call_answers_it() -> None:
    """chat-eval #339: the review turn took two model steps (call review_answer, then answer);
    the server reviews a doubt first and the model answers in one."""
    chat, tools = Chat("c3f9a1b2c4d5"), Tools(ask_drawings=LEVELLED)
    counted(chat, tools)
    model = Model(final(text="Not for certain: it is Low [ev_4].", evidence_ids=["ev_4"]))
    got = again(chat, model, tools, "Are you sure?")
    assert len(model.sent) == 1  # one model call
    asked = model.sent[0][-1]["content"]
    assert asked.startswith("Are you sure?\n" + REVIEWED)
    assert json.loads(asked.split(REVIEWED, 1)[1])["drawings"][0]["level"] == "low"
    assert [(s.tool, s.label) for s in got.steps] == [("review_answer", "Reviewed the last answer")]
    assert len(got.answers) == 1 and got.view is not None


@pytest.mark.parametrize("doubt", ["Are you sure?", "I count 30. Could it be 30?"])
def test_a_reply_to_a_doubt_that_cites_nothing_keeps_the_answer_card_and_its_places(
    doubt: str,
) -> None:
    """chat-eval #339 (sure-pdf-doors t3, s1-windows t2-t3): a reply about the reviewed answer
    that cites no place lost the answer card, its number and the plan."""
    chat, tools = Chat("c3f9a1b2c4d5"), Tools(ask_drawings=LEVELLED)
    counted(chat, tools)
    model = Model(final(text="The count is a low-confidence estimate."))
    got = again(chat, model, tools, doubt)
    assert [e.id for e in got.evidence] == ["ev_1", "ev_2", "ev_3"]
    assert len(got.answers) == 1 and got.answers[0]["question"] == "how many doors"
    assert got.view is not None and len(got.view.marks) == 3


def test_a_question_that_only_contains_could_it_be_is_no_doubt() -> None:
    assert DOUBT.search("i count 30. could it be 30?")
    assert not DOUBT.search("could it be that the kitchen is the largest room?")


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


REFUSED: Json = {"question": "how big is the kitchen", "parts": [{
    "drawing_id": DRAWING, "name": "plan.pdf",
    "answer": {"answer": None, "refusal": {"text": "The drawing has no scale."}}}]}  # fmt: skip


def test_review_339_n2_a_refused_last_answer_is_called_a_refusal_that_stands() -> None:
    """Queue 6 (qa-a live): the card's kind and the text agree: an answer, not 'I don't know'."""
    got = sure(REFUSED)
    assert (got.kind, got.text) == (
        "answer",
        "Yes: the last answer was a refusal, and it stands. plan.pdf: The drawing has no scale.",
    )
    assert len(got.answers) == 1 and got.answers[0]["question"] == "how big is the kitchen"


def test_a_doubt_about_a_refusal_is_an_answer_not_i_dont_know() -> None:
    """Queue 6: live, Gemini replied kind dont_know with 'Yes, the drawing has no scale ...',
    so the card read 'I don't know.' over 'Yes, ...' and had no steps."""
    chat, tools = Chat("c3f9a1b2c4d5"), Tools(ask_drawings=REFUSED)
    again(chat, Model(step(call("ask_drawings", question="how big is the kitchen")),
                      final(kind="dont_know", text="The drawing has no scale.")),
          tools, "How big is the kitchen?")  # fmt: skip
    model = Model(final(kind="dont_know", text="Yes, the drawing has no scale, so no area."))
    got = again(chat, model, tools, "Are you sure?")
    assert got.kind == "answer" and got.text.startswith("Yes, the drawing has no scale")
    assert [s.tool for s in got.steps] == ["review_answer"]
    assert len(got.answers) == 1


def test_the_rules_planner_answers_a_pushed_number_from_the_review_and_keeps_the_card() -> None:
    chat, tools = Chat("c3f9a1b2c4d5"), Tools(ask_drawings=LEVELLED)
    rules = RulesChatModel()
    run_turn(chat, "How many doors are there?", (), rules, tools, Caps(), SpendGuard())
    got = run_turn(chat, "I count 30. Could it be 30?", (), rules, tools, Caps(), SpendGuard())
    assert [s.tool for s in got.steps] == ["review_answer"]
    assert [name for name, _ in tools.ran] == ["ask_drawings"]  # not asked again
    assert got.kind == "answer" and "30 is outside what the drawings show (2 to 4)" in got.text
    assert len(got.answers) == 1 and got.answers[0]["question"] == "how many doors"


def test_a_doubts_review_streams_as_its_first_step() -> None:
    chat, tools = Chat("c3f9a1b2c4d5"), Tools(ask_drawings=LEVELLED)
    counted(chat, tools)
    got: list[tuple[str, Any]] = []
    model = Model(final(text="Not for certain [ev_4].", evidence_ids=["ev_4"]))
    run_turn(chat, "Are you sure?", (), model, tools, Caps(), SpendGuard(), names=NAMES,
             emit=lambda kind, data: got.append((kind, data)))  # fmt: skip
    kinds = [(kind, data.get("tool")) for kind, data in got if kind != "thinking"]
    assert kinds[:3] == [("turn", None), ("tool_call", "review_answer"),
                         ("tool_result", "review_answer")]  # fmt: skip


# chat-eval #339 t3 (queue, 22:50): "I count 30. Could it be 30?" got "Yes, it could be 30" over a
# reading of 19 with 5 disputed marks. A pushed number outside what the drawings show is not agreed.
NINETEEN: Json = json.loads(json.dumps(DOORS))
NINETEEN["parts"][0]["answer"]["answer"] = 19


def test_pushback_the_review_gives_the_range_the_drawings_support() -> None:
    from app.core.agent.review import review_of

    [drawing] = review_of(NINETEEN, {})["drawings"]
    assert drawing["range"] == [18, 20]  # 19 with 1 disputed mark either way


def test_pushback_rules_mode_does_not_agree_with_a_number_outside_the_range() -> None:
    chat, tools, rules = Chat("c3f9a1b2c4d5"), Tools(ask_drawings=NINETEEN), RulesChatModel()
    run_turn(chat, "How many doors are there?", (), rules, tools, Caps(), SpendGuard())
    got = run_turn(chat, "I count 30. Could it be 30?", (), rules, tools, Caps(), SpendGuard())
    assert got.kind == "answer" and not got.text.lower().startswith("yes")
    assert "30 is outside what the drawings show (18 to 20)" in got.text
    inside = run_turn(chat, "Could it be 20?", (), rules, tools, Caps(), SpendGuard())
    assert "20 is within what the drawings show (18 to 20)" in inside.text


def test_pushback_gemini_text_that_agrees_with_an_unmeasured_number_is_sent_back() -> None:
    chat, tools = Chat("c3f9a1b2c4d5"), Tools(ask_drawings=NINETEEN)
    counted(chat, tools)
    model = Model(
        final(text="Yes, it could be 30: the count is a low-confidence estimate."),
        final(text="The drawings show 19 doors [ev_1], not 30."),
    )
    got = again(chat, model, tools, "I count 30. Could it be 30?")
    assert "30" in model.sent[1][-1]["content"] and "outside" in model.sent[1][-1]["content"]
    assert got.text.startswith("The drawings show 19 doors")


def test_review_339b_m1_a_new_questions_dont_know_stays_dont_know() -> None:
    """A doubt-looking message after a refusal, then a new ask the model can't answer."""
    chat, tools = Chat("c3f9a1b2c4d5"), Tools(ask_drawings=REFUSED)
    again(chat, Model(step(call("ask_drawings", question="how big is the kitchen")),
                      final(kind="dont_know", text="No scale.")), tools)  # fmt: skip
    model = Model(step(call("ask_drawings", question="windows")),
                  final(kind="dont_know", text="I don't know the windows."))  # fmt: skip
    got = again(chat, model, tools, "I count 4 windows. Is that right?")
    assert got.kind == "dont_know"


@pytest.mark.parametrize(
    "message",
    [
        "Is it correct that the kitchen has a window?",
        "Is that right for the second floor too?",
        "I count 3 bedrooms. How many bathrooms are there?",
        "Could it be 2 storeys high?",
        "Is it right to count the closet doors?",
    ],
)
def test_review_339b_m2_new_questions_are_no_doubt(message: str) -> None:
    assert not DOUBT.search(message.lower())


@pytest.mark.parametrize("message", ["I count 30. Could it be 30?", "Is that right?", "I count 31.",
                                     "could it be 30 doors?"])  # fmt: skip
def test_review_339b_m2_doubts_still_match(message: str) -> None:
    assert DOUBT.search(message.lower())
