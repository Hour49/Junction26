"""QA round 1 on the agent loop (agent/law-check 7b4545f; ids from .agents/qa-law/TRIAGE.md), with
a scripted model: each test names its QA id and the spec id it holds."""

import json
from typing import Any

from test_agent_law import LAW
from test_agent_loop import ASKED, PROPOSAL, Model, Tools, call, final, step, turn

from app.adapters.agent_tools import _pack_default  # pyright: ignore[reportPrivateUsage]
from app.core.agent.loop import STOPS, UNBACKED
from app.core.agent.prompt import NO_COUNTRY, SYSTEM
from app.core.agent.validate import SHORTENED, TEXT_CHARS
from app.core.spend import SpendGuard

URL = "https://www.zh.ch/content/dam/700.1_7.9.75_131.pdf"
CLAUSE = {"id": "ch-zh-ls-700-1-302", "ref": "§ 302", "url": URL,
          "text": "Die Räume müssen genügend belichtet sein. " * 6}  # fmt: skip
LONG = f"PBG § 302 ({URL}) asks for daylight in every room. " * 30


def test_answers_2_robust_5_ac14_a_too_long_answer_is_cut_at_a_sentence_not_unbacked() -> None:
    model = Model(step(call("get_clause", clause_id=CLAUSE["id"])),
                  final(text=LONG), final(text=LONG, n=10))  # fmt: skip
    got = turn(model, Tools(get_clause=CLAUSE))
    retry = model.sent[2][-1]["content"]
    assert f"too long ({len(LONG)} characters): shorten it to {TEXT_CHARS}" in retry
    assert got.kind == "answer" and got.text != UNBACKED
    assert len(got.text) <= TEXT_CHARS and got.text.endswith("daylight in every room." + SHORTENED)


def test_answers_2_ac4_numbers_and_refs_from_a_law_tool_back_the_answer() -> None:
    text = f"PBG § 302 asks for daylight; see {URL}."
    got = turn(Model(step(call("get_clause", clause_id=CLAUSE["id"])), final(text=text)),
               Tools(get_clause=CLAUSE))  # fmt: skip
    assert (got.kind, got.text) == ("answer", text)


def test_robust_2_ac2_the_total_budget_does_not_say_this_hour() -> None:
    total, hourly = SpendGuard(total_usd=0.01), SpendGuard(per_hour_usd=0.01)
    total.charge(0.02)
    hourly.charge(0.02)
    assert turn(Model(), guard=total).text == "The assistant's spending budget is used up."
    assert turn(Model(), guard=hourly).text == STOPS["budget_hour"]


def test_lawai_1_lc14_would_not_meet_with_nothing_behind_it_gets_a_retry_then_goes() -> None:
    said = "The bathroom is 8.9 m2 [ev_1]. It would not meet § 303 of the PBG."
    model = Model(step(call("ask_drawings", question="area")),
                  final(text=said), final(text=said, n=10))  # fmt: skip
    asked = {**ASKED, "parts": [{**ASKED["parts"][0], "answer": {
        **ASKED["parts"][0]["answer"], "answer": 8.9}}], "note": "PBG § 303"}  # fmt: skip
    got = turn(model, Tools(ask_drawings=asked))
    assert "nothing this turn backs it" in model.sent[2][-1]["content"]
    assert (got.kind, got.text) == ("answer", "The bathroom is 8.9 m2 [1].")


def test_lawai_1_lc8_would_not_meet_on_a_failing_law_check_finding_stands() -> None:
    model = Model(step(call("propose_remove_wall", wall_id="W4")),
                  final(kind="edit", text="It would not meet the area rule [ev_1].",
                        proposal_id="p1"))  # fmt: skip
    got = turn(model, Tools(propose_remove_wall={**PROPOSAL, "law": LAW}))
    assert got.text == "It would not meet the area rule [1]."


def test_answers_9_ac9_a_conflicting_quantity_ends_as_conflict() -> None:
    part = ASKED["parts"][0]
    quantity = {"status": "conflict", "values": [22.4, 30.0]}
    asked = {**ASKED, "parts": [{**part, "answer": {**part["answer"], "quantity": quantity}}]}
    got = turn(Model(step(call("ask_drawings", question="area")),
                     final(text="Room 1.01 is on two drawings.")),
               Tools(ask_drawings=asked))  # fmt: skip
    assert got.kind == "conflict"
    assert "kind conflict" in SYSTEM  # the prompt says so too


def test_r4_c9_different_rooms_values_are_not_a_conflict_the_model_says_they_are() -> None:
    """Tudor QA R4-C9: "The sources disagree." (kind conflict) over three different rooms'
    values, while the card under it said each is its own room. A conflict is two sources giving
    one quantity different values: a turn is a conflict only when a quantity it rests on is one."""
    part = ASKED["parts"][0]
    parts = [
        {**part, "drawing_id": f"d{n}", "name": f"flat-{n}.pdf",
         "answer": {**part["answer"], "answer": value}}
        for n, value in enumerate((7.56, 9.1, 12.4), start=1)
    ]  # fmt: skip
    asked = {**ASKED, "parts": parts}
    said = "Room 1.01 is 7.56, 9.1 and 12.4 m2 on the three flats [ev_1] [ev_2] [ev_3]."
    got = turn(Model(step(call("ask_drawings", question="area of room 1.01")),
                     final(kind="conflict", text=said)),
               Tools(ask_drawings=asked))  # fmt: skip
    assert got.kind == "answer"  # the text and its three sources as they were
    assert got.text == "Room 1.01 is 7.56, 9.1 and 12.4 m2 on the three flats [1] [2] [3]."
    assert len(got.answers) == 1 and len(got.evidence) == 3  # the card stays with the turn


def test_r4_c9_a_conflicting_quantity_the_model_calls_a_conflict_stays_one() -> None:
    part = ASKED["parts"][0]
    quantity = {"status": "conflict", "values": [22.4, 30.0]}
    asked = {**ASKED, "parts": [{**part, "answer": {**part["answer"], "quantity": quantity}}]}
    got = turn(Model(step(call("ask_drawings", question="area")),
                     final(kind="conflict", text="Room 1.01 is 22.4 or 30.0 m2 [ev_1].")),
               Tools(ask_drawings=asked))  # fmt: skip
    assert got.kind == "conflict"


def test_answers_3_lc6_the_turn_context_follows_the_system_prompt_every_turn() -> None:
    model = Model(final(text="Pick a country."))
    turn(model, context=NO_COUNTRY)
    system = model.sent[0][0]
    assert system["role"] == "system" and system["content"] == f"{SYSTEM}\n{NO_COUNTRY}"


def test_answers_1_ac31_the_prompt_asks_for_plain_text() -> None:
    assert "plain text only: no Markdown" in SYSTEM


def test_answers_3_lc6_search_law_without_a_pack_gets_the_turns() -> None:
    ran: list[Any] = []
    run = _pack_default(lambda name, args: ran.append(json.loads(args)) or "{}", "fi",
                        "search_law", json.dumps({"query": "bedroom"}))  # fmt: skip
    _pack_default(lambda name, args: ran.append(json.loads(args)) or "{}", "fi", "search_law",
                  json.dumps({"query": "bedroom", "pack": "ch-zh"}))  # fmt: skip
    assert run == "{}" and [given["pack"] for given in ran] == ["fi", "ch-zh"]


def room_step() -> Any:
    """propose_room with a name (call() takes `name` for the tool's own name)."""
    args = {"selection_id": "sel_1", "name": "Storage"}
    return step({"id": "c1", "type": "function",
                 "function": {"name": "propose_room", "arguments": json.dumps(args)}})  # fmt: skip


def test_edits_6_ac6_step_labels_in_plain_words_and_a_refused_proposal_is_a_failed_step() -> None:
    refused = {"status": "refused", "reason": "the area is outside every room"}
    got = turn(Model(room_step(), final(kind="dont_know", text="I could not place it.")),
               Tools(propose_room=refused))  # fmt: skip
    (only,) = got.steps
    assert (only.label, only.status) == (
        "Could not place a room Storage in the drawn area",
        "error",
    )
    (ok,) = turn(
        Model(room_step(), final(text="Done.")), Tools(propose_room={"status": "ok"})
    ).steps
    assert (ok.label, ok.status) == ("Proposed a room Storage in the drawn area", "ok")


# QA rerun minors
def test_rerun_edits_n1_ac6_no_selection_or_proposal_id_reaches_the_text() -> None:
    from app.core.agent.loop import _plain_ids  # pyright: ignore[reportPrivateUsage]

    said = (
        "I placed it (sel_1); accept or reject the proposal p1, then ask again for sel_2 (sel_2)."
    )
    assert _plain_ids(said) == (
        "I placed it; accept or reject the proposal, then ask again for the second area you drew."
    )
    assert (
        _plain_ids("sel_0 and sel_12, p2.")
        == "an area you drew and an area you drew, the proposal."
    )
    assert "Never write selection ids (sel_1) or proposal ids (p1)" in SYSTEM


def test_rerun_edits_n2_ac6_a_missing_argument_still_gives_plain_words() -> None:
    walls = step(call("propose_remove_wall", room_a="R1", room_b="R2"))
    got = turn(Model(walls, final(text="Done.")), Tools(propose_remove_wall={"status": "ok"}))
    assert got.steps[0].label == "Proposed removing a wall"
    no_wall = {"status": "refused", "reason": "no wall"}
    refused = turn(Model(walls, final(kind="dont_know", text="No.")),
                   Tools(propose_remove_wall=no_wall))  # fmt: skip
    assert refused.steps[0].label == "Could not remove a wall"
    other = turn(Model(step(call("list_walls", page=1)), step(call("made_up_tool", n=2)),
                       final(text="Done.")),
                 Tools(list_walls={"status": "ok"}, made_up_tool={"status": "ok"}))  # fmt: skip
    assert [s.label for s in other.steps] == ["Listed the walls of a drawing", "Made up tool"]


# Smoke after #309
def test_smoke_1_ac31_a_room_by_type_word_or_label_and_number_is_asked_as_room_number() -> None:
    from app.adapters.agent_tools import room_by_number

    assert room_by_number("How big is bathroom 1.01?") == "How big is room 1.01?"
    assert room_by_number("How big is Bagno 1.01?") == "How big is room 1.01?"
    assert room_by_number("bathroom 1.01 and Cucina 1.03") == "room 1.01 and room 1.03"
    for kept in ("How big is room 1.01?", "Is room 1.01 bigger than 7.50?", "scale 1.50",
                 "Is it 7.50 m2?", "How big is the bathroom?"):  # fmt: skip
        assert room_by_number(kept) == kept
    assert 'as "room 1.01"' in SYSTEM  # the Gemini path is told too
