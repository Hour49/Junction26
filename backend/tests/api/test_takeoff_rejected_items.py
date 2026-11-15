"""A door the surveyor rejected on the sheet's door row still counted on the per-room door rows
(Tudor's QA round 4, R4-B2): an edit was kept under its own row's key only, and a room's door row
is another key over the same doors. Synthetic: one kitchen with two doors in its walls."""

from typing import Any

from app.api.takeoff import takeoff_rows
from app.core.drawing.model import Drawing, Element, Page, Room, Scale
from app.core.pipeline.takeoff import known_quantities
from app.core.review.model import Edit, ReviewState
from app.core.review.review import apply, sign, with_rejected_items

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
