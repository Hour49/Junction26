"""An IFC model's facts count by type and storey, never by room (sample services-mep, 2026-11-15):
"How many radiators are in the kitchen?" on the DigitalHub heating model answered the model's 63.
A count inside one room is refused with the one-room words; the model's own counts, a storey's,
a flat's and a room's own facts (its area, the spaces of a type) are answered as before."""

import pytest

from app.core.answering.facts import FACTS, answer_from_facts
from app.core.answering.model import IN_ONE_ROOM, Answer, Question
from app.core.ifc_facts import Fact, FactSheet

_HEATING = FactSheet(
    model="hzg",
    disciplines=["heating"],
    facts=[
        Fact(topic="space_heater.count", subject="all", value=63, unit="count",
             discipline="heating", source="ifc"),
        Fact(topic="space_heater.count", subject="all", value=29, unit="count",
             discipline="heating", source="ifc", storey="E00_OKRD"),
        Fact(topic="space_heater.count", subject="all", value=34, unit="count",
             discipline="heating", source="ifc", storey="E01_OKRD"),
    ],
)  # fmt: skip


def _answer(text: str) -> Answer | None:
    return answer_from_facts(Question(id=1, file="hzg.ifc", text=text), _HEATING, 0.0)


@pytest.mark.parametrize(
    "text",
    [
        "How many radiators are in the kitchen?",
        "How many radiators are in the cafeteria?",
        "How many radiators are in room 1-2?",
        "How many radiators does the kitchen have?",
        "How many radiators are in the kitchen on the ground floor?",
    ],
)
def test_a_count_inside_one_room_of_a_model_is_refused(text: str) -> None:
    answer = _answer(text)
    assert answer is not None and answer.answer is None and answer.abstain, answer
    assert answer.method == "refused:unsupported-question" and answer.explanation == IN_ONE_ROOM
    assert "63" not in str(answer.answer) and "29" not in str(answer.answer)


@pytest.mark.parametrize(
    ("text", "number"),
    [
        ("How many radiators are there?", "63"),
        ("How many radiators are in the building?", "63"),
        ("How many radiators are in the model?", "63"),
        ("How many radiators are in the heating system?", "63"),
        ("How many radiators are on the ground floor?", "29"),
        ("How many radiators are in the apartment?", "63"),
    ],
)
def test_a_count_of_the_whole_model_or_a_storey_is_answered_as_before(
    text: str, number: str
) -> None:
    answer = _answer(text)
    assert answer is not None and answer.method == FACTS and number in str(answer.answer), answer
