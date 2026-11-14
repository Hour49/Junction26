"""Counts that point at nothing (r8 BM, from think-acc's judge's path, fix 5): on a flagged page a
room count with no located mark is refused like an element count the reader found nothing of; on
a clean page a count with no mark says "not located on the drawing" next to the value; and a door
count asked "including closet doors" says the counting rule."""

import pytest
from test_review_core import BOX_A, BOX_B, PHOTO_FLAG, asked_flagged, photo

from app.core.drawing.model import Element, Room
from app.core.pipeline.model import Quantity
from app.core.review import ask as review_ask
from app.core.review.ask import CLOSET_RULE, NOT_LOCATED

KITCHEN = Room(id="r1", type="kitchen", page=1, box=BOX_B)
DOOR = Element(id="e1", class_="door", page=1, box=BOX_A)


def test_a_room_count_with_no_mark_on_a_flagged_page_is_refused() -> None:
    """The phone photo answered "0 bathrooms" with nothing marked: a guess, not a count."""
    drawing = photo(KITCHEN, elements=(DOOR,))
    found = asked_flagged("How many bathrooms are there?", drawing, (PHOTO_FLAG,))
    assert found.refusal is not None and found.refusal.code == "no-reader"
    assert "none of what its reader counted here is located on it" in found.refusal.text
    assert "0 would be a guess" in found.refusal.text
    kitchens = asked_flagged("How many kitchens are there?", drawing, (PHOTO_FLAG,))
    assert kitchens.refusal is None and kitchens.answer.answer == 1  # marked: still a count
    windows = asked_flagged("How many windows are there?", drawing, (PHOTO_FLAG,))
    assert windows.refusal is None and windows.answer.answer == 0  # an element read 0 (R3-qa4-1)


def test_the_same_room_count_on_a_clean_page_is_answered() -> None:
    found = asked_flagged("How many bathrooms are there?", photo(KITCHEN, elements=(DOOR,)), ())
    assert found.refusal is None and found.answer.answer == 0


def test_a_count_with_no_mark_on_a_clean_page_says_it_is_not_located(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The big scan answered "3 toilets" with nothing marked on the plan."""
    known = review_ask.known_quantities

    def unmarked_toilets(drawing):  # type: ignore[no-untyped-def]
        found = dict(known(drawing))
        found["toilet"] = Quantity(key="toilet", value=3, unit="count", marks=(), rule="count")
        return found

    monkeypatch.setattr(review_ask, "known_quantities", unmarked_toilets)
    drawing = photo(KITCHEN, elements=(DOOR,))
    found = asked_flagged("How many toilets are there?", drawing, ())
    assert found.answer.answer == 3 and found.answer.explanation is not None
    assert NOT_LOCATED in found.answer.explanation
    doors = asked_flagged("How many doors are there?", drawing, ())
    assert NOT_LOCATED not in (doors.answer.explanation or "")  # marked: nothing to say


def test_a_door_count_including_closet_doors_says_the_rule() -> None:
    drawing = photo(KITCHEN, elements=(DOOR,))
    found = asked_flagged("How many doors are there, including closet doors?", drawing, ())
    assert found.answer.answer == 1 and CLOSET_RULE in (found.answer.explanation or "")
    plain = asked_flagged("How many doors are there?", drawing, ())
    assert CLOSET_RULE not in (plain.answer.explanation or "")
