"""A door the surveyor rejected on the sheet's door row still counted on the per-room door rows
(Tudor's QA round 4, R4-B2): an edit was kept under its own row's key only, and a room's door row
is another key over the same doors. Synthetic: one kitchen with two doors in its walls."""

from collections.abc import Callable
from typing import Any

import pytest

from app.api.takeoff import SignOffRequest, review, signoff, takeoff_rows
from app.core.drawing.model import Drawing, Element, Page, Room, Scale
from app.core.pipeline.takeoff import known_quantities
from app.core.review.model import Edit, ReviewState
from app.core.review.review import (
    NotAllowedError,
    ValueChangedError,
    apply,
    sign,
    with_rejected_items,
)

KITCHEN = ((0.1, 0.1), (0.5, 0.1), (0.5, 0.5), (0.1, 0.5))  # page fractions
DOORS = (
    Element(id="d1", class_="door", page=1, box=(0.28, 0.09, 0.32, 0.11)),  # in the north wall
    Element(id="d2", class_="door", page=1, box=(0.49, 0.28, 0.51, 0.32)),  # in the east wall
)
ROOM_DOORS = "door|name=kitchen"


def drawing() -> Drawing:
    return Drawing(
        file="x.pdf",
        pages=(Page(page=1, width=100, height=100, unit="pt"),),
        scale=Scale(status="scaled", m_per_unit=0.01),
        rooms=(
            Room(
                id="r1",
                type="kitchen",
                label="Kitchen",
                page=1,
                box=(0.1, 0.1, 0.5, 0.5),
                polygon=KITCHEN,
            ),
        ),
        elements=DOORS,
    )


class Store:
    """Just what `takeoff_rows` asks of the ingest and the review store."""

    def __init__(self, state: ReviewState) -> None:
        self.state = state

    def drawing(self, drawing_id: str) -> Drawing:
        return drawing()

    def get(self, project: str | None, drawing_id: str) -> ReviewState:
        return self.state

    def update(
        self, project: str | None, drawing_id: str, change: Callable[[ReviewState], ReviewState]
    ) -> None:
        self.state = change(self.state)


def rejected(key: str, element: Element) -> ReviewState:
    """`element`'s mark rejected on row `key`, as the surveyor's Reject stores it."""
    found = known_quantities(drawing())[key]
    at = next(n for n, mark in enumerate(found.marks, 1) if mark.box == element.box)
    edit = Edit(quantity=key, action="reject", mark=f"m{at}")
    return apply(ReviewState(), edit, found, drawing(), "2026-11-15T05:30:00Z")


def rows(state: ReviewState) -> dict[str, Any]:
    store: Any = Store(state)
    return {found.key: found for found in takeoff_rows("d1", store, store, zeros=True).quantities}


def test_the_room_counts_two_doors_as_the_sheet_does() -> None:
    found = rows(ReviewState())
    assert (found["door"].value, found[ROOM_DOORS].value) == (2, 2)


def test_a_door_rejected_on_the_sheet_row_drops_out_of_the_rooms_door_row() -> None:
    found = rows(rejected("door", DOORS[0]))
    assert found["door"].value == 1
    room = found[ROOM_DOORS]
    assert room.value == 1
    assert [(mark.box, mark.state) for mark in room.marks if mark.state == "rejected"] == [
        (DOORS[0].box, "rejected")
    ]


def test_a_door_rejected_on_a_rooms_row_stays_in_the_sheet_count() -> None:
    """A door between two rooms is both rooms': "not this room's" is not "not a door"."""
    found = rows(rejected(ROOM_DOORS, DOORS[0]))
    assert (found["door"].value, found[ROOM_DOORS].value) == (2, 1)


def test_the_rooms_row_signs_off_the_count_it_shows() -> None:
    state = rejected("door", DOORS[0])
    quantity = known_quantities(drawing())[ROOM_DOORS]
    shown = with_rejected_items(state, known_quantities(drawing()))
    signed = sign(state, quantity, drawing(), "Tudor", "2026-11-15T05:31:00Z", shown=shown)
    assert signed.signed[ROOM_DOORS].value == 1
    assert signed.rejected == state.rejected  # what is shown is derived, never stored


def test_a_rooms_row_signs_off_with_the_value_the_client_showed() -> None:
    """With R4-B10's expected value (#634): the room's row shows 1 after its door was rejected on
    the sheet row, so a sign-off of 1 is the value shown and 2 is a stale one."""
    store: Any = Store(rejected("door", DOORS[0]))
    stale = SignOffRequest(quantity=ROOM_DOORS, by="Tudor", expected_value=2, expected_unit="count")
    with pytest.raises(ValueChangedError):
        signoff("d1", stale, store, store)
    assert ROOM_DOORS not in store.state.signed
    seen = SignOffRequest(quantity=ROOM_DOORS, by="Tudor", expected_value=1, expected_unit="count")
    signoff("d1", seen, store, store)
    assert store.state.signed[ROOM_DOORS].value == 1


def door_mark(key: str, element: Element) -> str:
    found = known_quantities(drawing())[key]
    return f"m{next(n for n, mark in enumerate(found.marks, 1) if mark.box == element.box)}"


def test_a_sheet_reject_is_refused_while_a_room_row_it_would_change_is_signed() -> None:
    """review-640 M1: the room's row signed at 2 must not show 1 under its sign-off."""
    store: Any = Store(ReviewState())
    signoff("d1", SignOffRequest(quantity=ROOM_DOORS, by="Tudor"), store, store)
    reject = Edit(quantity="door", action="reject", mark=door_mark("door", DOORS[0]))
    with pytest.raises(NotAllowedError, match="door\\|name=kitchen is signed off by Tudor"):
        review("d1", reject, store, store)
    found = rows(store.state)
    assert (found["door"].value, found[ROOM_DOORS].value) == (2, 2)
    assert found[ROOM_DOORS].signed is not None and found[ROOM_DOORS].signed.value == 2


def test_a_looks_right_room_row_holds_the_sheet_restore_until_it_is_unsettled() -> None:
    """review-640 S1: reject on the sheet, "looks right" on the room (settled and signed 1),
    unsign, restore on the sheet: the room must not keep a settled 1 over two counted doors."""
    store: Any = Store(ReviewState())
    mark = door_mark("door", DOORS[0])
    review("d1", Edit(quantity="door", action="reject", mark=mark), store, store)
    signoff("d1", SignOffRequest(quantity=ROOM_DOORS, by="Tudor", settle=True), store, store)
    signoff("d1", SignOffRequest(quantity=ROOM_DOORS, by="Tudor", undo=True), store, store)
    restore = Edit(quantity="door", action="restore", mark=mark)
    with pytest.raises(NotAllowedError, match="has a settled value"):
        review("d1", restore, store, store)
    review("d1", Edit(quantity=ROOM_DOORS, action="unsettle"), store, store)
    review("d1", restore, store, store)
    found = rows(store.state)
    assert (found["door"].value, found[ROOM_DOORS].value) == (2, 2)


def test_a_settled_room_row_holds_the_sheet_reject_until_it_is_unsettled() -> None:
    """review-640 nit: a settled 2 with one of its marks shown rejected contradicts itself."""
    store: Any = Store(ReviewState())
    review("d1", Edit(quantity=ROOM_DOORS, action="settle", value=2), store, store)
    reject = Edit(quantity="door", action="reject", mark=door_mark("door", DOORS[0]))
    with pytest.raises(NotAllowedError, match="has a settled value"):
        review("d1", reject, store, store)
    assert rows(store.state)[ROOM_DOORS].value == 2
