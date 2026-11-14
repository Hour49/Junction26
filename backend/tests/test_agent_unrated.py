"""Levels only where measured (phase 2 item 4, orchestrator option 2): a number read from the
drawing's geometry, takeoff or walls has no confidence level, so an answer whose number rests
only on such a place says so in one plain sentence, added by the server (never a retry)."""

from typing import Any

from test_agent_loop import ASKED, PROPOSAL, Model, Tools, call, final, step, turn

from app.core.agent.loop import UNRATED

DRAWING = "0123456789abcdef"
GEOMETRY: dict[str, Any] = {
    "drawing_id": DRAWING, "page": 1,
    "rooms": [{"id": "R1", "label": "LOBBY 104", "area_m2": 14.2, "page": 1,
               "box": [0.1, 0.1, 0.3, 0.3]}],
}  # fmt: skip


def test_a_number_read_from_geometry_only_gets_the_unrated_sentence() -> None:
    model = Model(
        step(call("get_plan_geometry", drawing_id=DRAWING, page=1)),
        final(text="The lobby is 14.2 m² [ev_1].", evidence_ids=["ev_1"]),
    )
    got = turn(model, Tools(get_plan_geometry=GEOMETRY), message="How big is the lobby?")
    assert got.kind == "answer"
    assert got.text == f"The lobby is 14.2 m² [1]. {UNRATED}"
    assert not any(c.isdigit() for c in UNRATED)  # the number check never sees new numbers
    assert len(model.sent) == 2  # no retry


def test_a_number_ask_drawings_rated_needs_no_sentence() -> None:
    model = Model(
        step(
            call("ask_drawings", question="bathroom"),
            call("get_plan_geometry", 2, drawing_id=DRAWING, page=1),
        ),
        final(text="The bathroom is 7.56 m² [ev_1].", evidence_ids=["ev_1"]),
    )
    got = turn(model, Tools(ask_drawings=ASKED, get_plan_geometry=GEOMETRY))
    assert UNRATED not in got.text


def test_a_number_the_user_gave_needs_no_sentence() -> None:
    model = Model(
        step(call("get_plan_geometry", drawing_id=DRAWING, page=1)),
        final(
            text="I can't tell whether it is 14.2 m²; the lobby is drawn [ev_1].",
            evidence_ids=["ev_1"],
        ),
    )
    got = turn(model, Tools(get_plan_geometry=GEOMETRY), message="Is the lobby 14.2 m2?")
    assert UNRATED not in got.text


def test_edits_and_refusals_are_left_as_they_are() -> None:
    edit = Model(
        step(call("propose_remove_wall", wall_id="W4")),
        final(kind="edit", text="The merged room is 24.69 m².", proposal_id="p1"),
    )
    assert UNRATED not in turn(edit, Tools(propose_remove_wall=PROPOSAL)).text
    dont = Model(
        step(call("get_plan_geometry", drawing_id=DRAWING, page=1)),
        final(kind="dont_know", text="The lobby's 14.2 m² is drawn but I can't confirm it."),
    )
    assert UNRATED not in turn(dont, Tools(get_plan_geometry=GEOMETRY)).text
