"""The agent loop with a scripted model (spec AC-1..AC-9)."""

import json
from typing import Any

import pytest

from app.adapters.chat_rules import RulesChatModel
from app.core.agent.loop import NUDGE, STOPS, UNBACKED, run_turn
from app.core.agent.model import Caps, Chat, ChatTurn
from app.core.agent.ports import ChatModelError, Reply
from app.core.agent.prompt import SYSTEM
from app.core.plan_edit.model import Proposal, Selection
from app.core.spend import SpendGuard

Json = dict[str, Any]
DRAWING = "0123456789abcdef"
ASKED = {
    "question": "how big is the bathroom",
    "parts": [{
        "drawing_id": DRAWING, "name": "plan.pdf",
        "answer": {"answer": 7.56, "unit": "m2", "line": {"sure": True},
                   "level": {"level": "high", "basis": "vector", "text": "Read from vectors."},
                   "marks": [{"id": "m1", "page": 1, "box": [0.1, 0.2, 0.3, 0.4],
                              "label": "Bagno 1.01"}]},
    }],
}  # fmt: skip
PROPOSAL = {
    "status": "ok",
    "proposal": {
        "proposal_id": "p1", "drawing_id": DRAWING, "page": 1,
        "removed": [{"id": "W4", "polygon": [[0.4, 0.2], [0.41, 0.2], [0.41, 0.3]],
                     "label": "Wall W4"}],
        "rooms": [{"id": "R1+R2", "label": "Bagno 1.01 + Stanza 1.02",
                   "polygon": [[0.3, 0.2], [0.5, 0.2], [0.5, 0.3]],
                   "area_before_m2": 24.04, "area_after_m2": 24.69, "was": ["R1", "R2"]}],
        "unknowns": ["Whether wall W4 is load-bearing: this drawing does not say."],
    },
}  # fmt: skip


def call(name: str, n: int = 1, **arguments: Any) -> Json:
    return {"id": f"c{n}", "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments)}}  # fmt: skip


def step(*calls: Json, **extra: Any) -> Reply:
    return Reply({"role": "assistant", "content": None, "tool_calls": list(calls), **extra}, 0.0)


def final(kind: str = "answer", text: str = "Done.", n: int = 9, **more: Any) -> Reply:
    return step(call("final_answer", n, kind=kind, text=text, **more))


class Model:
    name = "scripted"

    def __init__(self, *replies: Reply) -> None:
        self.replies = list(replies)
        self.sent: list[list[Json]] = []
        self.tools: list[Json] = []

    def complete(self, messages: list[Json], tools: list[Json]) -> Reply:
        self.sent.append(json.loads(json.dumps(messages)))
        self.tools = tools
        if not self.replies:
            raise AssertionError("the model was called more often than scripted")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class Tools:
    def __init__(self, **results: Any) -> None:
        self.results = results
        self.ran: list[tuple[str, str]] = []

    @property
    def tools(self) -> list[Json]:
        return [{"type": "function", "function": {"name": name}} for name in self.results]

    def run(self, name: str, arguments: str) -> str:
        self.ran.append((name, arguments))
        found = self.results.get(name, {"error": f"unknown tool {name}"})
        return found if isinstance(found, str) else json.dumps(found)

    def proposal(self, proposal_id: str) -> Proposal | None:
        return None

    def describe(self, selection: Selection) -> str:
        return f"{selection.id}: room {selection.ref}"


CAPS = Caps()


def turn(model: Model, tools: Tools | None = None, chat: Chat | None = None,
         caps: Caps = CAPS, guard: SpendGuard | None = None, message: str = "How big?",
         **more: Any) -> ChatTurn:  # fmt: skip
    tools = tools or Tools(ask_drawings=ASKED)
    selection = more.pop("selection", ())
    chat = chat or Chat("c3f9a1b2c4d5")
    return run_turn(chat, message, selection, model, tools, caps, guard or SpendGuard(), **more)


def test_ac1_ac5_ac6_answer_cites_minted_evidence_and_lists_steps() -> None:
    model = Model(
        step(call("ask_drawings", question="how big is the bathroom")),
        final(text="The bathroom Bagno 1.01 is 7.56 m² [ev_1].", evidence_ids=["ev_1"]),
    )
    got = turn(model)
    assert (got.kind, got.text, got.turn) == (
        "answer",
        "The bathroom Bagno 1.01 is 7.56 m² [1].",
        1,
    )
    [evidence] = got.evidence
    assert (evidence.n, evidence.id, evidence.name, evidence.label) == (1, "ev_1", "plan.pdf",
                                                                       "Bagno 1.01")  # fmt: skip
    assert evidence.box == (0.1, 0.2, 0.3, 0.4) and evidence.sure is True
    assert evidence.level is not None and evidence.level.level == "high"
    [only] = got.steps
    assert (only.tool, only.label, only.status) == (
        "ask_drawings",
        "Asked the drawings: how big is the bathroom",
        "ok",
    )
    assert got.model == "scripted"
    tool_message = model.sent[1][-1]
    assert tool_message["role"] == "tool" and '"ev":"ev_1"' in tool_message["content"]
    assert model.sent[0][0] == {"role": "system", "content": SYSTEM}
    assert model.tools[-1]["function"]["name"] == "final_answer"


def test_ac4_a_number_no_tool_gave_is_sent_back_once() -> None:
    model = Model(
        step(call("ask_drawings", question="q")),
        final(text="It is 9.99 m²."),
        final(text="It is 7.6 m² [ev_1].", evidence_ids=["ev_1"], n=10),
    )
    got = turn(model)
    assert got.kind == "answer" and got.text == "It is 7.6 m² [1]."  # 7.56 rounded to 1 decimal
    refusal = model.sent[2][-1]
    assert "9.99" in refusal["content"] and "error" in refusal["content"]


def test_ac4_second_failure_becomes_dont_know() -> None:
    model = Model(
        step(call("ask_drawings", question="q")),
        final(text="It is 9.99 m²."),
        final(text="It is 99 m² [ev_7].", evidence_ids=["ev_7"], n=10),
    )
    got = turn(model)
    assert (got.kind, got.text, got.evidence) == ("dont_know", UNBACKED, ())


def test_ac4_numbers_in_the_users_message_count_and_citations_do_not() -> None:
    model = Model(final(text="You asked about 3 rooms [1]."))
    got = turn(model, Tools(), message="What about my 3 rooms?")
    assert got.kind == "answer"


def test_ac4_edit_needs_a_proposal_of_this_turn() -> None:
    model = Model(
        final(kind="edit", text="Removed.", proposal_id="p1"),
        step(call("propose_remove_wall", wall_id="W4")),
        final(kind="edit", text="Removing wall W4 makes 24.69 m².", proposal_id="p1", n=10),
    )
    chat = Chat("c3f9a1b2c4d5")
    got = turn(model, Tools(propose_remove_wall=PROPOSAL), chat)
    assert got.kind == "edit" and got.edit is not None
    assert got.edit.rooms[0].area_after_m2 == 24.69 and got.edit.state == "proposed"
    assert "proposal_id" in model.sent[1][-1]["content"]
    assert chat.proposals["p1"] == got.edit
    assert got.steps[0].label == "Proposed removing wall W4"


def test_ac4_answer_on_failed_tools_only_is_refused() -> None:
    model = Model(
        step(call("list_walls", drawing_id=DRAWING, page=1)),
        final(text="The walls are fine."),
        final(kind="dont_know", text="This plan is a scan.", n=10),
    )
    got = turn(model, Tools(list_walls={"status": "cannot_edit", "reason": "a scan"}))
    assert got.kind == "dont_know" and "failed" in model.sent[2][-1]["content"]


def test_ac4_needs_input_carries_its_options() -> None:
    options = [{"label": "Bagno 1.01", "message": "the first"},
               {"label": "Bagno 1.05", "message": "the second"}]  # fmt: skip
    got = turn(Model(final(kind="needs_input", text="Which bathroom?", options=options)), Tools())
    assert got.kind == "needs_input" and got.options and got.options[1].label == "Bagno 1.05"


def test_options_go_out_on_any_kind() -> None:
    options = [{"label": "door count", "message": "How many doors are there?"}]
    got = turn(Model(final(kind="dont_know", text="I don't know.", options=options)), Tools())
    assert got.options and got.options[0].message == "How many doors are there?"


def test_evidence_and_steps_use_the_drawings_plain_name() -> None:
    model = Model(
        step(call("ask_drawings", question="q")),
        final(text="See [ev_1].", evidence_ids=["ev_1"]),
    )
    got = turn(model, names={DRAWING: "Drawn plan 1"})
    assert got.evidence[0].name == "Drawn plan 1"


def test_ac2_step_cap() -> None:
    model = Model(*(step(call("ask_drawings", question=f"q{n}")) for n in range(3)))
    got = turn(model, caps=Caps(max_steps=3))
    assert (got.kind, got.text, len(got.steps)) == ("dont_know", STOPS["steps"], 3)


def test_ac2_ac7_turn_spend_cap_and_charges() -> None:
    expensive = [Reply(step(call("ask_drawings", question=f"q{n}")).message, 0.06)
                 for n in range(3)]  # fmt: skip
    guard = SpendGuard()
    got = turn(Model(*expensive), guard=guard)
    assert (got.kind, got.text) == ("dont_know", STOPS["turn_usd"])
    assert got.cost_usd == pytest.approx(0.12) and guard.spent_by() == {"agent chat": 0.12}


def test_ac2_spend_guard_exhausted_before_any_call() -> None:
    guard = SpendGuard(total_usd=0.01)
    guard.charge(0.02)
    model = Model()
    got = turn(model, guard=guard)
    assert (got.kind, got.text, model.sent) == ("dont_know", STOPS["budget"], [])


def test_ac2_time_cap() -> None:
    ticks = iter(range(0, 1000, 40))
    model = Model(*(step(call("ask_drawings", question=f"q{n}")) for n in range(5)))
    got = turn(model, caps=Caps(seconds=60), clock=lambda: next(ticks))
    assert got.text == STOPS["seconds"]


def test_ac2_the_same_call_a_third_time_stops() -> None:
    model = Model(*(step(call("ask_drawings", n, question="q")) for n in range(3)))
    tools = Tools(ask_drawings=ASKED)
    got = turn(model, tools)
    assert (got.text, len(tools.ran)) == (STOPS["repeat"], 2)


def test_ac3_no_tool_call_is_nudged_once() -> None:
    silent = Reply({"role": "assistant", "content": "Hmm."}, 0.0)
    model = Model(silent, silent)
    got = turn(model)
    assert model.sent[1][-1] == {"role": "user", "content": NUDGE}
    assert (got.kind, got.text) == ("dont_know", STOPS["silent"])


def test_model_error_is_a_dont_know() -> None:
    got = turn(Model(ChatModelError("HTTP 503")))  # type: ignore[arg-type]
    assert got.kind == "dont_know" and "HTTP 503" in got.text


def test_r7_a_failed_but_paid_model_call_is_charged() -> None:
    guard = SpendGuard()
    got = turn(Model(ChatModelError("no message", usd=0.05)), guard=guard)  # type: ignore[arg-type]
    assert got.kind == "dont_know" and got.cost_usd == 0.05
    assert guard.spent_by() == {"agent chat": 0.05}


def test_a_tool_error_goes_back_to_the_model_and_marks_the_step() -> None:
    model = Model(
        step(call("get_takeoff", drawing_id=DRAWING)),
        final(kind="dont_know", text="I could not read it."),
    )
    got = turn(model, Tools(get_takeoff={"error": "project is running"}), names={DRAWING: "a.pdf"})
    assert got.steps[0].status == "error" and got.steps[0].label == "Read the quantities of a.pdf"
    assert "project is running" in model.sent[1][-1]["content"]


def test_ac8_assistant_message_with_extra_content_is_sent_back_verbatim() -> None:
    signed = call("ask_drawings", question="q")
    signed["extra_content"] = {"google": {"thought_signature": "c2lnbmF0dXJl"}}
    first = step(signed, reasoning="kept")
    model = Model(first, final(text="Ok [ev_1].", evidence_ids=["ev_1"]))
    turn(model)
    assert model.sent[1][2] == first.message


def test_at_most_four_calls_per_step_each_answered() -> None:
    calls = [call("ask_drawings", n, question=f"q{n}") for n in range(5)]
    model = Model(step(*calls), final(kind="dont_know", text="No."))
    tools = Tools(ask_drawings=ASKED)
    got = turn(model, tools)
    replies = [m for m in model.sent[1] if m["role"] == "tool"]
    assert len(tools.ran) == 4 and len(got.steps) == 4
    assert [m["tool_call_id"] for m in replies] == [f"c{n}" for n in range(5)]
    assert "at most 4" in replies[4]["content"]


def test_ac13_long_results_are_cut_for_the_model_and_kept_whole() -> None:
    big = {"rows": [{"x": "x" * 100, "box": [0.1, 0.1, 0.2, 0.2], "note": None}] * 100}
    chat = Chat("c3f9a1b2c4d5")
    model = Model(
        step(call("get_takeoff", drawing_id=DRAWING)), final(kind="dont_know", text="No.")
    )
    turn(model, Tools(get_takeoff=big), chat)
    seen = json.loads(model.sent[1][-1]["content"])  # still JSON, geometry and nulls left out
    assert seen["rows"] == [{"x": "x" * 100}] * 50 and seen["rows_more"] == 50  # typed items
    assert chat.results[0]["result"] == big


def test_ac13_a_result_too_long_even_cut_ends_with_a_note() -> None:
    big = {"text": "y" * 9000}
    model = Model(
        step(call("get_takeoff", drawing_id=DRAWING)), final(kind="dont_know", text="No.")
    )
    turn(model, Tools(get_takeoff=big))
    assert model.sent[1][-1]["content"].endswith('{"truncated": true}')


def test_ac12_selection_lines_follow_the_message() -> None:
    chosen = Selection(id="sel_1", kind="room", drawing_id=DRAWING, page=1, ref="R3")
    model = Model(final(kind="dont_know", text="No."))
    turn(model, Tools(), selection=[chosen], message="Make this larger")
    assert model.sent[0][1] == {"role": "user", "content": "Make this larger\nsel_1: room R3"}


def test_ac23_later_turns_see_six_turns_and_old_tool_results_cut() -> None:
    chat = Chat("c3f9a1b2c4d5")
    big = {"rows": ["x" * 100] * 30}
    models = [Model(step(call("get_takeoff", drawing_id=DRAWING)),
                    final(kind="dont_know", text="No.")) for _ in range(7)]  # fmt: skip
    got = [turn(model, Tools(get_takeoff=big), chat) for model in models][-1]
    model = models[-1]
    assert got.turn == 7 and len(chat.turns) == 7
    sent = model.sent[0]
    assert sum(m["role"] == "user" for m in sent) == 6
    assert all(len(m["content"]) <= 1000 for m in sent if m["role"] == "tool")


def test_evidence_ids_run_on_through_the_chat() -> None:
    chat = Chat("c3f9a1b2c4d5")
    for n in (1, 2):
        model = Model(step(call("ask_drawings", question="q")),
                      final(text=f"See [ev_{n}].", evidence_ids=[f"ev_{n}"]))  # fmt: skip
        got = turn(model, chat=chat)
        assert got.kind == "answer" and got.evidence[0].id == f"ev_{n}"


THREE = {
    "question": "how many doors",
    "parts": [{"drawing_id": DRAWING, "name": "plans/a.pdf", "answer": {"answer": 3, "marks": [
        {"id": f"m{n}", "page": 1, "box": [0.1, 0.1, 0.2, 0.2], "label": "door"}
        for n in (1, 2, 3)]}}],
}  # fmt: skip


def test_ac5_evidence_is_only_what_the_text_cites_in_its_order() -> None:
    model = Model(
        step(call("ask_drawings", question="q")),
        final(text="Doors [ev_3] and [ev_1].", evidence_ids=["ev_1", "ev_2", "ev_3"]),
    )
    got = turn(model, Tools(ask_drawings=THREE))
    assert got.text == "Doors [1] and [2]."
    assert [(e.n, e.id) for e in got.evidence] == [(1, "ev_3"), (2, "ev_1")]


def test_the_text_names_drawings_by_their_plain_name() -> None:
    model = Model(
        step(call("ask_drawings", question="q")),
        final(text="plans/a.pdf: 3 doors [ev_1]."),
    )
    got = turn(model, Tools(ask_drawings=THREE), names={DRAWING: "Drawn plan 1"})
    assert got.text == "Drawn plan 1: 3 doors [1]."
    unmarked = {"parts": [{"drawing_id": DRAWING, "name": "model/house.ifc",
                           "answer": {"answer": 2, "marks": []}}]}  # fmt: skip
    model = Model(step(call("ask_drawings", question="q")), final(text="model/house.ifc: 2."))
    got = turn(model, Tools(ask_drawings=unmarked), names={DRAWING: "Building model"})
    assert got.text == "Building model: 2."


def test_answers_are_the_cited_ask_drawings_results_as_given() -> None:
    model = Model(
        step(call("ask_drawings", question="q")),
        final(text="3 doors [ev_2]."),
    )
    got = turn(model, Tools(ask_drawings=THREE))
    assert got.answers == (THREE,)  # without the ev ids the server added for the model


def test_a_dont_know_on_a_refusal_carries_that_result() -> None:
    answer = {"answer": None, "refusal": {"text": "No scale."}}
    refused = {"parts": [{"drawing_id": DRAWING, "name": "a.pdf", "answer": answer}]}
    model = Model(step(call("ask_drawings", question="q")),
                  final(kind="dont_know", text="No scale."))  # fmt: skip
    assert turn(model, Tools(ask_drawings=refused)).answers == (refused,)


def test_answers_without_citations() -> None:
    model = Model(step(call("ask_drawings", question="q")), final(text="See below."))
    assert turn(model, Tools(ask_drawings=THREE)).answers == (THREE,)  # an answer: every result
    walls = {"walls": [{"id": "W1", "page": 1, "box": [0.1, 0.1, 0.2, 0.2]}],
             "drawing_id": DRAWING}  # fmt: skip
    model = Model(step(call("ask_drawings", question="q"), call("list_walls", 2)),
                  final(text="Wall W1 [ev_4].", evidence_ids=["ev_4"]))  # fmt: skip
    assert turn(model, Tools(ask_drawings=THREE, list_walls=walls)).answers == ()


def test_get_counting_rules_has_a_plain_step_label() -> None:
    """Queue 3 (#353): the steps line said 'Get counting rules'."""
    rules = {"quantity": "doors", "rule": "each door opening counts once."}
    model = Model(
        step(call("get_counting_rules", quantity="closet doors")),
        step(call("get_counting_rules", 2)),
        final(kind="dont_know", text="No."),
    )
    got = turn(model, Tools(get_counting_rules=rules))
    assert [s.label for s in got.steps] == [
        "Read what counts as closet doors",
        "Read the counting rules",
    ]


def test_queue_1_an_estimated_area_reaches_the_model_in_whole_m2() -> None:
    """The ask result showed 5 but carried the raw 4.88 (quantity, line): the model said 4.88."""
    shown = {"question": "kitchen area", "parts": [{"drawing_id": DRAWING, "name": "plan.pdf",
             "answer": {"answer": 5, "unit": "m2",
                        "quantity": {"value": 4.88, "unit": "m2", "estimate": {"basis": "doors"}},
                        "line": {"answer": 4.88, "unit": "m2", "estimate": "doors"},
                        "marks": []}}]}  # fmt: skip
    model = Model(step(call("ask_drawings", question="kitchen area")),
                  final(text="The kitchen is 4.88 m²."),
                  final(text="The kitchen is about 5 m²."))  # fmt: skip
    got = turn(model, Tools(ask_drawings=shown))
    assert "4.88" not in model.sent[1][-1]["content"]
    assert got.text == "The kitchen is about 5 m²."  # 4.88 is no longer backed


def test_tudor_nit_a_measured_area_reaches_the_model_as_the_card_shows_it() -> None:
    """Tudor's smoke: the reply said 7.557 m2 while the card said 7.56 m²."""
    shown = {"question": "kitchen area", "parts": [{"drawing_id": DRAWING, "name": "plan.pdf",
             "answer": {"answer": 7.557, "unit": "m2",
                        "quantity": {"value": 7.557, "unit": "m2"},
                        "line": {"answer": 7.557, "unit": "m2"},
                        "marks": []}}]}  # fmt: skip
    model = Model(step(call("ask_drawings", question="kitchen area")),
                  final(text="The kitchen is 7.557 m²."),
                  final(text="The kitchen is 7.56 m²."))  # fmt: skip
    got = turn(model, Tools(ask_drawings=shown))
    assert "7.557" not in model.sent[1][-1]["content"]
    assert got.text == "The kitchen is 7.56 m²."  # 7.557 is no longer backed


HALL = {"question": "What is the area of the Multi-Purpose Hall?", "parts": [
    {"drawing_id": DRAWING, "name": "school.png", "answer": {
        "answer": 156, "unit": "m2", "marks": [{"id": "m1", "page": 1, "box": [0.1, 0.1, 0.2, 0.2],
                                               "label": "Multi-Purpose Hall"}]}}]}  # fmt: skip


def test_an_answer_that_leaves_the_value_to_the_card_says_it() -> None:
    """Live 2026-11-15 (T1 school): "What is the area of the Multi-Purpose Hall?" got "The area of
    the Multi-Purpose Hall is shown below [1]." with no number: the prompt sends the values to the
    card under the text. The server adds each answering drawing's value, as the rules lead says
    it (R2-A6), when the text states none."""
    below = "The area of the Multi-Purpose Hall is shown below [ev_1]."
    model = Model(step(call("ask_drawings", question=HALL["question"])), final(text=below))
    got = turn(model, Tools(ask_drawings=HALL))
    assert got.text.startswith("The area of the Multi-Purpose Hall is shown below [1].")
    assert got.text.endswith(": 156 m².") and got.answers, got.text


def test_an_answer_that_states_its_value_is_left_as_it_is() -> None:
    model = Model(step(call("ask_drawings", question=HALL["question"])),
                  final(text="The Multi-Purpose Hall is 156 m² [ev_1]."))  # fmt: skip
    assert turn(model, Tools(ask_drawings=HALL)).text == "The Multi-Purpose Hall is 156 m² [1]."


def test_466_the_lead_cites_every_drawing_the_card_shows_though_parts_are_cut() -> None:
    """#466 (Mada's look-check): 4 drawings answered, the card showed 4, the rules lead said "The
    drawing answers this below [1].": the planner read the result cut for the model's window, where
    `parts` kept 1 drawing. The model's copy now lists every answering drawing in `answered`."""
    marks = [{"id": f"m{k}", "page": 1, "box": [0.1, 0.1, 0.2, 0.2],
              "label": f"door {k} " + "x" * 40} for k in range(30)]  # fmt: skip
    parts = [{"drawing_id": f"{DRAWING[:-1]}{n}", "name": f"{n}.pdf", "answer": {
        "answer": 30, "unit": "count", "quantity": {"noun": "doors"}, "marks": marks,
        "explanation": "y" * 900}} for n in range(1, 5)]  # fmt: skip
    model = RulesChatModel()
    got = turn(model, Tools(ask_drawings={"question": "how many doors", "parts": parts}))  # pyright: ignore[reportArgumentType]
    assert len(got.answers[0]["parts"]) == 4  # the card
    assert got.text == "1.pdf: 30 [1]; 2.pdf: 30 [2]; 3.pdf: 30 [3]; 4.pdf: 30 [4]."  # each drawing


def test_every_answering_drawing_reaches_the_model_though_parts_are_cut() -> None:
    """qa-a demo walk: 'which drawing has the largest floor area' on 6 drawings: the model's copy
    kept 1 part of 6, so it could not compare them. `answered` lists each one that answered."""
    marks = [{"id": f"m{k}", "page": 1, "box": [0.1, 0.2, 0.3, 0.4], "label": f"Room {k} " * 9}
             for k in range(25)]  # fmt: skip
    parts = [{"drawing_id": f"{n:016x}", "name": f"plan-{n}.pdf",
              "answer": {"answer": 10.0 + n, "unit": "m2", "marks": marks}}
             for n in range(5)]  # fmt: skip
    refused = {"drawing_id": f"{9:016x}", "name": "scan.png",
               "answer": {"answer": None, "refusal": {"text": "Not read."}}}  # fmt: skip
    asked = {"question": "What is the total floor area?", "parts": [*parts, refused]}
    model = Model(step(call("ask_drawings", question="What is the total floor area?")),
                  final(kind="dont_know", text="No."))  # fmt: skip
    turn(model, Tools(ask_drawings=asked))
    seen = json.loads(model.sent[1][-1]["content"])
    assert seen["parts_more"] >= 1  # the cut this is about
    assert [(a["drawing"], a["answer"], a["unit"]) for a in seen["answered"]] == [
        (f"plan-{n}.pdf", 10.0 + n, "m2") for n in range(5)]  # fmt: skip
    assert [a["ev"] for a in seen["answered"]] == [f"ev_{1 + 25 * n}" for n in range(5)]


def test_review_483_answered_is_never_cut_though_each_part_is_8_kb() -> None:
    """qa-c review of #483 (MUST 1): once `parts` was cut to one drawing, `answered` was the
    longest list and got halved too (13 drawings of ~8 KB each: the model saw 6). It is built
    first and kept whole; only the rest is cut."""
    marks = [{"id": f"m{k}", "page": 1, "box": [0.1, 0.2, 0.3, 0.4], "label": f"Room {k}"}
             for k in range(10)]  # fmt: skip
    parts = [{"drawing_id": f"{n:016x}", "name": f"plan-{n}.pdf",
              "answer": {"answer": 10.0 + n, "unit": "m2", "marks": marks,
                         "explanation": "x" * 7500}}
             for n in range(13)]  # fmt: skip
    asked = {"question": "What is the total floor area?", "parts": parts}
    model = Model(step(call("ask_drawings", question="What is the total floor area?")),
                  final(kind="dont_know", text="No."))  # fmt: skip
    turn(model, Tools(ask_drawings=asked))
    content = model.sent[1][-1]["content"]
    assert len(content) <= 8000
    seen = json.loads(content)
    assert "answered_more" not in seen
    assert [a["drawing"] for a in seen["answered"]] == [f"plan-{n}.pdf" for n in range(13)]
