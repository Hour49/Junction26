"""The agent loop's building-rule checks on an edit turn (spec plan-edit-law-check LC-8, LC-9a..c),
with a scripted model and the plan tool's result as plain JSON."""

import json
from typing import Any

import pytest
from test_agent_loop import DRAWING, PROPOSAL, Model, Tools, call, final, step, turn
from test_plan_edit_law_check import (
    BEDROOM,
    GOOD,
    LEFT_WINDOW,
    clause,
    drawing,
    packs,
    storage_in_bedroom,
)

from app.core.agent.model import Chat
from app.core.agent.validate import FINAL_ANSWER_TOOL
from app.core.plan_edit.law_check import check_proposal
from app.core.plan_edit.model import Proposal

Json = dict[str, Any]

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


# LC-9b/c with law-kb's real LawCheck and ClauseView: the 12 m2 bedroom shrunk to 9 m2 by a
# storage room, its law check as the plan tool returns it (app/adapters/plan_tools._proposed)
class LawTools(Tools):
    """The plan tool's result and the full proposal (law included) the loop asks the toolbox for."""

    def __init__(self, pack: str) -> None:
        made = storage_in_bedroom()
        law = check_proposal(drawing(BEDROOM, elements=(LEFT_WINDOW,)), made, packs()[pack],
                             "vector", related=(clause(),))  # fmt: skip
        self.made = made.model_copy(update={"law": law})
        view = law.for_model()
        for given in view["findings"]:
            given["box"] = list(BEDROOM.box)
        shown = {"status": "ok", "proposal": made.model_dump(mode="json"),
                 "law": {"drawing_id": made.drawing_id, "page": 1, **view}}  # fmt: skip
        super().__init__(propose_room=shown)

    def proposal(self, proposal_id: str) -> Proposal | None:
        return self.made if proposal_id == "p1" else None


def law_turn(pack: str, *answers: Any, chat: Chat | None = None) -> Any:
    model = Model(step(call("propose_room", selection_id="sel_1")), *answers)
    tools = LawTools(pack)
    return turn(model, tools, chat), model, tools


NOTE = GOOD.model_dump()  # PBG § 303: Schlafzimmer 9.0 >= 10 m2, would_not_meet


def test_lc9b_a_correct_note_lands_in_the_edit_with_the_servers_quote() -> None:
    text = "The Schlafzimmer would be 9 m², under the 10 m2 of § 303."
    got, model, _ = law_turn("fi", edit_with(text, [NOTE]))
    assert got.kind == "edit" and got.edit.law is not None, model.sent[-1][-1]
    (kept,) = got.edit.law.ai_findings
    assert (kept.ref, kept.verdict, kept.basis) == ("§ 303", "would_not_meet", "ai_reading")
    assert kept.quote.startswith("Wohn-") and kept.url == "https://www.zh.ch/pbg"


def test_lc10_the_chat_keeps_the_proposal_as_shown_for_accept() -> None:
    chat = Chat("c3f9a1b2c4d5")
    text = "The Schlafzimmer would be 9 m² [ev_1], under the 10 m2 of § 303."
    got, _, _ = law_turn("fi", edit_with(text, [NOTE]), chat=chat)
    assert got.edit is not None and chat.proposals["p1"] == got.edit
    kept = chat.proposals["p1"].law
    assert kept is not None
    assert kept.findings[0].ev == "ev_1" and kept.ai_findings[0].ref == "§ 303"


BAD_NOTES: list[Json] = [
    {"limit": 8},
    {"clause_id": "ch-zh-ls-700-1-302-2"},
    {"value": 8.5},
    {"verdict": "meets"},
    {"subject": "Wohnzimmer"},
]


@pytest.mark.parametrize("change", BAD_NOTES)
def test_lc9b_a_note_that_does_not_stand_gets_a_retry_and_never_lands(change: Json) -> None:
    text = "The Schlafzimmer would be 9 m², under the 10 m2 of § 303."
    got, model, _ = law_turn("fi", edit_with(text, [{**NOTE, **change}]),
                             edit_with("A storage room.", [], 10))  # fmt: skip
    assert "dropped" in model.sent[2][-1]["content"]
    assert got.kind == "edit" and got.edit.law is not None and not got.edit.law.ai_findings


def test_lc9c_a_kept_would_not_meet_note_must_be_named_by_its_ref() -> None:
    got, model, _ = law_turn("fi", edit_with("A storage room.", [NOTE]),
                             edit_with("A storage room.", [NOTE], 10))  # fmt: skip
    assert "§ 303" in model.sent[2][-1]["content"]
    assert got.kind == "edit" and got.text.endswith("see Building rules.")
    assert got.edit.law.ai_findings  # the note stood; only its naming was fixed by the server


def test_lc7_each_finding_keeps_the_ev_id_the_model_cited() -> None:
    got, _, tools = law_turn("ch-zh", edit("The Schlafzimmer would be 9 m2 [ev_1]."))
    shown = tools.results["propose_room"]["law"]["findings"]
    assert got.kind == "edit" and got.edit.law is not None
    assert [f.ev for f in got.edit.law.findings] == [f"ev_{n}" for n in range(1, len(shown) + 1)]
    assert got.edit.law.findings[0].change == "newly_fails"
    assert (got.evidence[0].id, got.evidence[0].label) == ("ev_1", "Schlafzimmer")


def edit_with(text: str, notes: list[Json], n: int = 9) -> Any:
    return final(kind="edit", text=text, proposal_id="p1", law_notes=notes, n=n)
