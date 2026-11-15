"""'on the plumbing plan' names the drawing, not a room (big QA R1 services, row 12/10 note,
pic-det, 2026-11-15): P-101's own Ask refused "How many WCs are shown on the plumbing plan?" with
"This question counts what is inside one room, and I count across the whole drawing", a
whole-sheet count read as one room's because "plumbing" is no sheet word. A discipline word before
a sheet word ("the heating plan", "the ventilation drawing") is the sheet; "the plumbing room"
stays a room."""

import pytest
from test_levels import POLICY, SCAN, Scored

from app.adapters.answer_prior import NoPrior
from app.adapters.question_templates import TemplateParser
from app.core.answering.facts import FACTS
from app.core.answering.model import IN_ONE_ROOM, Query, Unsupported
from app.core.ifc_facts import Fact, FactSheet, Spot
from app.core.review.ask import Asked, ask
from app.core.review.model import ReviewState

PARSE = TemplateParser().parse
SERVICES = "the sheet-kind step calls this page a services plan"  # triage.symbols_refused's flag


@pytest.mark.parametrize(
    ("text", "subject"),
    [
        ("How many WCs are shown on the plumbing plan?", "toilet"),
        ("How many toilets are on the plumbing sheet?", "toilet"),
        ("How many doors are on the ventilation drawing?", "door"),
        ("How many windows are shown on this heating plan?", "window"),
        ("How many doors are on the HVAC layout?", "door"),
        ("How many sinks are on the sanitary drawing?", "sink"),
        ("How many doors are on the plumbing floor plan?", "door"),
        # review-711 M2: a capitalised discipline is no storey name or code ("MEP" is 3 capitals)
        ("How many WCs are on the Plumbing plan?", "toilet"),
        ("How many doors are on the MEP plan?", "door"),
        ("How many doors are on the HVAC plan?", "door"),
    ],
)
def test_a_discipline_s_plan_is_the_whole_sheet(text: str, subject: str) -> None:
    parsed = PARSE(text)
    assert isinstance(parsed, Query), (text, parsed)
    assert (parsed.measure, parsed.subject, parsed.name, parsed.storey) == (
        "count",
        subject,
        None,
        None,
    ), (text, parsed)


@pytest.mark.parametrize(
    "text",
    [  # review-711 M1: a part of the building, not a drawing of it (as on main)
        "How many doors are on the mechanical floor?",
        "How many doors are in the services building?",
        "How many toilets are in the sanitary unit?",
        "How many doors are in the power house?",
        "How many windows are on the electrical storey?",
    ],
)
def test_a_discipline_s_part_of_the_building_is_not_the_sheet(text: str) -> None:
    assert PARSE(text) == Unsupported(reason=IN_ONE_ROOM), text


@pytest.mark.parametrize(
    ("text", "storey"),
    [
        ("How many doors are on the P1 plan?", "P1"),
        ("How many doors are on the Erdgeschoss?", "Erdgeschoss"),
        ("How many doors are on level OG2?", "OG2"),
    ],
)
def test_a_real_storey_still_scopes(text: str, storey: str) -> None:
    parsed = PARSE(text)
    assert isinstance(parsed, Query) and parsed.storey == storey, (text, parsed)


@pytest.mark.parametrize(
    "text",
    [
        "How many WCs are in the plumbing room?",  # a room named by its use
        "How many doors are in the kitchen on the plumbing plan?",  # still one room
    ],
)
def test_a_room_is_still_a_room(text: str) -> None:
    assert PARSE(text) == Unsupported(reason=IN_ONE_ROOM)


def asked(text: str, facts: FactSheet | None) -> Asked:
    return ask(
        text, SCAN, parser=TemplateParser(), clock=lambda: 0.0, prior=NoPrior(),
        state=ReviewState(), confidence=Scored(0.9), raster=True, check=POLICY, route="raster",
        facts=None if facts is None else (lambda: facts), no_symbols=SERVICES,
    )  # fmt: skip


def test_a_services_sheet_says_why_it_does_not_count_not_one_room() -> None:
    """With no picture facts, the refusal is the services sheet's, never the one-room one."""
    found = asked("How many WCs are shown on the plumbing plan?", None)
    assert found.refusal is not None
    assert "inside one room" not in found.refusal.text, found.refusal.text
    assert "services plan" in found.refusal.text, found.refusal.text


def test_with_the_picture_s_facts_the_plan_s_wcs_are_answered_from_them() -> None:
    spot = Spot(page=1, box=(0.1, 0.1, 0.12, 0.12), reader="vlm")
    sheet = FactSheet(
        model="p101",
        disciplines=["plumbing"],
        facts=[
            Fact(topic="sanitary_terminal.count", subject=subject, value=8, unit="count",
                 discipline="plumbing", source="picture:vlm:held", spots=(spot,) * 8)
            for subject in ("all", "WC UP-Spülkasten Betätigung vorne:35 x 60cm")
        ],
    )  # fmt: skip
    found = asked("How many WCs are shown on the plumbing plan?", sheet)
    assert found.answer.method == FACTS and found.refusal is None, found.refusal
    assert found.answer.sure is None or found.answer.sure is False
