"""The agent loop's building-rule checks on an edit turn (spec plan-edit-law-check LC-8, LC-9a..c),
with a scripted model and the plan tool's result as plain JSON."""

import json
from typing import Any

import pytest
from test_agent_loop import DRAWING, PROPOSAL, Model, Tools, call, final, step, turn

from app.core.agent.validate import FINAL_ANSWER_TOOL

LAW = {
    "pack": "ch-zh", "pack_name": "Canton of Zürich building act", "drawing_id": DRAWING, "page": 1,
    "findings": [{"rule_id": "ch-zh-room-area", "change": "newly_fails", "subject": "Stanza 1.02",
                  "title": "A bedroom or living room is at least 10 m2", "limit": 10, "unit": "m2",
                  "after": {"status": "fail", "value": 8.9}, "box": [0.3, 0.2, 0.5, 0.3]}],
}  # fmt: skip
CHECKED = {**PROPOSAL, "law": LAW}  # the finding gets ev_1


def edit(text: str, n: int = 9) -> Any:
    return final(kind="edit", text=text, proposal_id="p1", n=n)


def run(*answers: Any) -> Any:
    model = Model(step(call("propose_remove_wall", wall_id="W4")), *answers)
    return turn(model, Tools(propose_remove_wall=CHECKED)), model


def test_lc8_an_edit_citing_its_failing_rule_passes() -> None:
    got, _ = run(edit("Stanza 1.02 would be 8.9 m², under the 10 m2 rule [ev_1]."))
    assert got.kind == "edit" and got.text.endswith("[1].")


def test_lc8_an_uncited_failing_rule_gets_one_retry_then_the_servers_sentence() -> None:
    got, model = run(edit("Proposed: a storage room."), edit("Done: a storage room.", 10))
    assert "ev_1" in model.sent[2][-1]["content"]  # the retry names the finding to cite
    assert got.kind == "edit" and got.text == (
        "Done: a storage room. This change would not meet 1 rule of Canton of Zürich building "
        "act: see Building rules.")  # fmt: skip


def test_lc8_the_retry_can_fix_it() -> None:
    got, _ = run(edit("Proposed."), edit("It would not meet the area rule [ev_1].", 10))
    assert got.text == "It would not meet the area rule [1]."


@pytest.mark.parametrize("word", ["illegal", "Legal", "COMPLIANT", "permitted"])
def test_lc8_banned_words_get_a_retry_then_their_sentence_goes(word: str) -> None:
    said = f"The new room is {word} here. It breaks the area rule [ev_1]."
    got, model = run(edit(said), edit(said, 10))
    assert word.lower() in model.sent[2][-1]["content"]
    assert got.kind == "edit" and got.text == "It breaks the area rule [1]."


def test_lc8_allowed_and_words_containing_them_are_fine() -> None:
    got, _ = run(edit("Walls are allowed here; legally-minded readers: see the rule [ev_1]."))
    assert got.kind == "edit" and "allowed" in got.text


def test_lc8_banned_words_on_any_kind() -> None:
    model = Model(final(kind="dont_know", text="Is it legal? I can't say."),
                  final(kind="dont_know", text="Is it legal? I can't say.", n=10))  # fmt: skip
    got = turn(model, Tools())
    assert (got.kind, got.text) == ("dont_know", "I can't say.")


def test_lc8_wording_never_turns_an_edit_into_dont_know() -> None:
    got, _ = run(edit("Illegal."), edit("Illegal.", 10))
    assert got.kind == "edit" and got.edit is not None
    assert got.text.startswith("The proposed change is shown below.")
    assert got.text.endswith("see Building rules.")


def test_lc9a_final_answer_takes_law_notes() -> None:
    notes = FINAL_ANSWER_TOOL["function"]["parameters"]["properties"]["law_notes"]
    assert notes["maxItems"] == 8
    schema = json.dumps(FINAL_ANSWER_TOOL)
    for field in ("clause_id", "subject", "comparison", "limit", "verdict", "would_not_meet"):
        assert field in schema


def test_lc9_notes_without_a_law_check_get_one_retry() -> None:
    note = {"clause_id": "c", "subject": "Stanza 1.02", "value": 8.9, "comparison": ">=",
            "limit": 10, "unit": "m2", "verdict": "would_not_meet"}  # fmt: skip
    model = Model(step(call("propose_remove_wall", wall_id="W4")),
                  final(kind="edit", text="Done.", proposal_id="p1", law_notes=[note]),
                  final(kind="edit", text="Done.", proposal_id="p1", n=10))  # fmt: skip
    got = turn(model, Tools(propose_remove_wall=PROPOSAL))
    assert got.kind == "edit" and "law_notes go only" in model.sent[2][-1]["content"]
