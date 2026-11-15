"""A count of 0 on a sheet whose element reader found no element of any kind is a blind 0, not a
count (big QA R1 services row 12: DigitalHub A-101, "0 elements, 26 rooms", answered "0 toilets"
High): the question is refused. A sheet that read elements and has none of the asked kind keeps
its 0 (app/core/review/ask.py _flagged)."""

import pytest

from app.adapters.answer_prior import NoPrior
from app.adapters.question_templates import TemplateParser
from app.core.drawing.model import Drawing, Element, Page, Room, Scale
from app.core.review.ask import Asked, ask
from app.core.review.model import ReviewState

PAGE = Page(page=1, width=1000, height=1000, unit="pt")
ROOMS = tuple(
    Room(id=f"r{n}", type="other", page=1, box=(0.1 * n, 0.1, 0.1 * n + 0.08, 0.2))
    for n in range(1, 4)
)
DOOR = Element(id="e1", class_="door", page=1, box=(0.5, 0.5, 0.52, 0.52))


def vector(*elements: Element) -> Drawing:
    """A vector sheet at a printed scale whose reader looked for doors, windows and fixtures."""
    return Drawing(
        file="A-101.pdf",
        pages=(PAGE,),
        scale=Scale(status="scaled", m_per_unit=0.01, source="1:100"),
        rooms=ROOMS,
        elements=elements,
        read=("door", "window", "toilet", "sink", "bathtub", "shower", "room"),
    )


def asked(text: str, drawing: Drawing) -> Asked:
    return ask(
        text, drawing, parser=TemplateParser(), clock=lambda: 0.0, prior=NoPrior(),
        state=ReviewState(),
    )  # fmt: skip


@pytest.mark.parametrize("question", ["How many toilets are there?", "How many doors are there?"])
def test_a_sheet_whose_reader_found_no_element_refuses_a_count_of_0(question: str) -> None:
    found = asked(question, vector())
    assert found.answer.answer is None
    assert found.refusal is not None and found.refusal.code == "no-reader"
    assert found.refusal.text == (
        "The reader found no doors, windows or fixtures of any kind on this drawing, so 0 would "
        "be a guess, not a count."
    )


def test_a_sheet_that_read_elements_keeps_its_0_of_another_kind() -> None:
    assert asked("How many toilets are there?", vector(DOOR)).answer.answer == 0
    assert asked("How many doors are there?", vector(DOOR)).answer.answer == 1


def test_rooms_are_still_counted_on_a_sheet_with_no_element() -> None:
    assert asked("How many rooms are there?", vector()).answer.answer == 3


WALL = Element(id="e2", class_="wall", page=1, box=(0.1, 0.3, 0.6, 0.31))


@pytest.mark.parametrize("question", ["How many toilets are there?", "How many doors are there?"])
def test_a_sheet_whose_reader_found_only_walls_refuses_a_count_of_0(question: str) -> None:
    """review-714 S1: walls (or columns, stairs) but no door, window or fixture of any kind is the
    same blind 0: "0 doors" High on a sheet whose symbols the reader did not see."""
    found = asked(question, vector(WALL))
    assert found.answer.answer is None, found.answer
    assert found.refusal is not None and found.refusal.code == "no-reader"
    assert "found no doors, windows or fixtures of any kind" in found.refusal.text


def test_a_reader_that_does_not_look_for_doors_says_so() -> None:
    """review-714 S2: a reader that reads only rooms was not asked for doors: its refusal says it
    does not look for them (as before #714), not that it found none."""
    rooms_only = vector().model_copy(update={"read": ("room",)})
    found = asked("How many doors are there?", rooms_only)
    assert found.refusal is not None and found.refusal.code == "not-read", found.refusal
    assert asked("How many rooms are there?", rooms_only).answer.answer == 3
