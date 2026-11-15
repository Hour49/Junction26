"""An IFC model's area total asked by a room word no space's name holds and no room type has
(sample explorers, 2026-11-15): "What is the total area of the garages?" on the vitoria model gave
"Spaces: 73 spaces, total area 903.07 m²" (every space), where one space is printed 0GARAJE
(19.18 m²). Such a question is refused; a total of the model, its floor or its spaces, and a word
of the model's own name ("the dental clinic"), answer as before."""

import pytest

from app.core.answering.facts import FACTS, answer_from_facts
from app.core.answering.model import Answer, Question
from app.core.ifc_facts import Fact, FactSheet


def fact(topic: str, subject: str, value: float | str, storey: str | None = None) -> Fact:
    unit = None if isinstance(value, str) else "m2"
    return Fact(
        topic=topic, subject=subject, value=value, unit=unit, storey=storey,
        discipline="architecture", source="test",
    )  # fmt: skip


VITORIA = FactSheet(
    model="vitoria",
    disciplines=["architecture"],
    facts=[
        fact("project.name", "all", "Vitoria Clinic"),
        fact("space.long_name", "01.11", "0GARAJE", storey="P0"),
        fact("space.long_name", "01.22", "1IZQ-SAL", storey="P1"),
        fact("space.long_name", "01.15", "1IZQ-HAB3", storey="P1"),
        fact("space.area", "01.11", 19.18, storey="P0"),
        fact("space.area", "01.22", 11.44, storey="P1"),
        fact("space.area", "01.15", 11.69, storey="P1"),
        fact("space.area", "all", 42.31),
        fact("space.count", "all", 3),
    ],
)


def _answer(text: str) -> Answer | None:
    return answer_from_facts(Question(id=1, file="vitoria.ifc", text=text), VITORIA, 0.0)


@pytest.mark.parametrize(
    "text",
    [
        "What is the total area of the garages?",
        "What is the total area of the offices?",
        "What is the total area of the office?",
        "What is the total office area?",
        "What is the total area of all rooms labelled Büro?",
        "What is the total area of all rooms labelled 'Büro'?",
    ],
)
def test_a_total_by_a_room_word_no_space_has_is_refused(text: str) -> None:
    answer = _answer(text)
    assert answer is not None and answer.answer is None and answer.abstain, answer
    assert "42.31" not in str(answer.explanation), answer.explanation


@pytest.mark.parametrize(
    "text",
    [
        "What is the total floor area?",
        "What is the total net floor area of the building?",
        "What is the total area of all spaces?",
        "What is the total area of the clinic?",  # the model's own name
    ],
)
def test_a_total_of_the_model_or_its_spaces_is_answered_as_before(text: str) -> None:
    answer = _answer(text)
    assert answer is not None and answer.method == FACTS and "42.31" in str(answer.answer), answer


@pytest.mark.parametrize(
    "text",
    ["What is the area of the 0GARAJE?", "What is the total area of the rooms named 0GARAJE?"],
)
def test_a_space_named_by_the_word_is_answered(text: str) -> None:
    answer = _answer(text)
    assert answer is not None and answer.method == FACTS and "19.18" in str(answer.answer), answer
