"""Levels only where measured (phase 2 item 4, orchestrator option 2): a number read from the
drawing's geometry, takeoff or walls has no confidence level, so an answer whose number rests
only on such a place says so in one plain sentence, added by the server (never a retry)."""

from typing import Any

from test_agent_loop import ASKED, PROPOSAL, Model, Tools, call, final, step, turn

from app.core.agent.loop import UNRATED, UNRATED_BOTH, UNRATED_TAKEOFF, run_turn
from app.core.agent.model import Caps, Chat
from app.core.spend import SpendGuard

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


TAKEOFF: dict[str, Any] = {
    "drawing_id": DRAWING,
    "rows": [{"quantity": "door", "count": 3, "marks": [{"id": "m9", "page": 2,
                                                         "box": [0.5, 0.5, 0.6, 0.6]}]}],
}  # fmt: skip
WALLS: dict[str, Any] = {
    "status": "ok", "drawing_id": DRAWING, "page": 1,
    "walls": [{"id": "W1", "length_m": 4.35, "rooms": [{"id": "r1", "label": "Bagno 1.01"}]}],
}  # fmt: skip


def takeoff(text: str, *first: Any, message: str = "How many doors?", **results: Any) -> str:
    model = Model(
        step(*first, call("get_takeoff", 9, drawing_id=DRAWING)),
        final(text=text),
    )
    return turn(model, Tools(**{"get_takeoff": TAKEOFF, **results}), message=message).text


def test_review_342_s1_a_takeoff_number_is_called_a_takeoff_number() -> None:
    assert takeoff("There are 3 doors.") == f"There are 3 doors. {UNRATED_TAKEOFF}"
    assert "geometry" not in UNRATED_TAKEOFF


def test_review_342_s1_numbers_from_takeoff_and_geometry_name_both() -> None:
    model = Model(
        step(call("get_takeoff", drawing_id=DRAWING),
             call("get_plan_geometry", 2, drawing_id=DRAWING, page=1)),
        final(text="There are 3 doors and the lobby is 14.2 m²."),
    )  # fmt: skip
    tools = Tools(get_takeoff=TAKEOFF, get_plan_geometry=GEOMETRY)
    assert turn(model, tools).text.endswith(UNRATED_BOTH)


def test_review_342_a_list_walls_number_is_geometry() -> None:
    model = Model(step(call("list_walls", drawing_id=DRAWING, page=1)),
                  final(text="Wall W1 is 4.35 m long."))  # fmt: skip
    assert turn(model, Tools(list_walls=WALLS)).text.endswith(UNRATED)


def test_review_342_s2_digits_inside_a_rated_result_do_not_rate_a_count() -> None:
    """ASKED holds page 1 and 'Bagno 1.01': neither rates the takeoff's 1 door."""
    one = {**TAKEOFF, "rows": [{**TAKEOFF["rows"][0], "count": 1}]}
    got = takeoff("There is 1 door.", call("ask_drawings", question="bathroom"),
                  ask_drawings=ASKED, get_takeoff=one)  # fmt: skip
    assert got.endswith(UNRATED_TAKEOFF)


def test_review_342_s2_a_floor_number_the_user_names_does_not_rate_a_count() -> None:
    got = takeoff("There are 3 doors.", message="How many doors on floor 3?")
    assert got.endswith(UNRATED_TAKEOFF)


def test_review_342_a_rated_answers_value_needs_no_sentence_earlier_turns_too() -> None:
    """The answer review_answer reviews and show_on_plan shows is an earlier turn's ask."""
    chat = Chat("c3f9a1b2c4d5")
    bathroom = {**GEOMETRY, "rooms": [{**GEOMETRY["rooms"][0], "area_m2": 7.56}]}
    tools = Tools(ask_drawings=ASKED, get_plan_geometry=bathroom)
    run_turn(chat, "How big is the bathroom?", (),
             Model(step(call("ask_drawings", question="bathroom")),
                   final(text="7.56 m² [ev_1].", evidence_ids=["ev_1"])),
             tools, Caps(), SpendGuard())  # fmt: skip
    later = Model(step(call("get_plan_geometry", drawing_id=DRAWING, page=1)),
                  final(text="Yes, the bathroom is 7.56 m²."))  # fmt: skip
    got = run_turn(chat, "Are you sure?", (), later, tools, Caps(), SpendGuard())
    assert UNRATED not in got.text


def test_review_342_n2_a_labels_number_is_a_name() -> None:
    model = Model(
        step(call("get_plan_geometry", drawing_id=DRAWING, page=1)),
        final(text="LOBBY 104 is drawn on the plan [ev_1].", evidence_ids=["ev_1"]),
    )
    assert UNRATED not in turn(model, Tools(get_plan_geometry=GEOMETRY)).text


def test_review_342_n3_not_said_twice() -> None:
    model = Model(
        step(call("get_plan_geometry", drawing_id=DRAWING, page=1)),
        final(text="The lobby is 14.2 m², read from the geometry without a confidence level."),
    )
    assert UNRATED not in turn(model, Tools(get_plan_geometry=GEOMETRY)).text


def test_a_drawings_name_is_a_name_not_a_number_from_geometry() -> None:
    """qa-a cross-drawing walk: "Which drawing has no scale?" → "Two drawings have no scale:
    Drawn plan 5 … and Plan photo 2 [1]." got "That number is read straight from the drawing's
    geometry" though it states no number: the 5 and 2 of the drawing names were read as numbers
    a geometry result backs. A number the answer states from geometry still gets it."""
    hall: dict[str, Any] = {
        "drawing_id": DRAWING, "page": 1, "scale": None,
        "rooms": [{"id": "R1", "label": "Hall", "area_m2": 5, "page": 1,
                   "box": [0.1, 0.1, 0.3, 0.3]}],
    }  # fmt: skip
    named = {DRAWING: "Drawn plan 5"}
    model = Model(
        step(call("get_plan_geometry", drawing_id=DRAWING, page=1)),
        final(text="Drawn plan 5 has no scale [ev_1].", evidence_ids=["ev_1"]),
    )
    got = turn(model, Tools(get_plan_geometry=hall), message="Which drawing has no scale?",
               names=named)  # fmt: skip
    assert got.text == "Drawn plan 5 has no scale [1]."
    model = Model(
        step(call("get_plan_geometry", drawing_id=DRAWING, page=1)),
        final(text="The hall on Drawn plan 5 is 5 m² [ev_1].", evidence_ids=["ev_1"]),
    )
    got = turn(model, Tools(get_plan_geometry=hall), names=named)
    assert got.text == f"The hall on Drawn plan 5 is 5 m² [1]. {UNRATED}"


def test_a_longer_drawing_name_goes_first() -> None:
    """ "Drawn plan 1" taken out of "Drawn plan 10" left a 0 that a geometry 0 backed."""
    empty: dict[str, Any] = {"drawing_id": DRAWING, "name": "Drawn plan 10", "page": 1, "doors": 0}
    model = Model(
        step(call("get_plan_geometry", drawing_id=DRAWING, page=1)),
        final(text="Drawn plan 10 has no scale."),
    )
    names = {"1" * 16: "Drawn plan 1", DRAWING: "Drawn plan 10"}
    got = turn(model, Tools(get_plan_geometry=empty), names=names)
    assert got.text == "Drawn plan 10 has no scale."
