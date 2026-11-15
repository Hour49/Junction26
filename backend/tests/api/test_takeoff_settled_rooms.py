"""A room's area settled on its own row still read the old value on the room's other rows (big QA
R1 row 12, describe): flat-b's kitchen settled at 22.40 kept "area of room (label Küche) 30.00"
and "area of room (indoor) 53.00". Synthetic: a kitchen printed 30 m² and a bathroom of 8 m²."""

from collections.abc import Callable
from typing import Any

from app.api.takeoff import takeoff_rows
from app.core.drawing.model import Apartment, Drawing, Page, Room, Scale
from app.core.pipeline.takeoff import known_quantities
from app.core.review.model import Edit, ReviewState
from app.core.review.review import apply, sign, with_rejected_items

AT = "2026-11-15T05:30:00Z"
KITCHEN, BATH = (0.1, 0.1, 0.5, 0.5), (0.5, 0.1, 0.7, 0.5)


def drawing(*, flat_m2: float | None = None, second: str = "Bad") -> Drawing:
    """`flat_m2`: an apartment around both rooms with its own (printed) area. `second`: the
    second room's label."""
    flat = "a1" if flat_m2 is not None else None
    return Drawing(
        file="x.pdf",
        pages=(Page(page=1, width=100, height=100, unit="pt"),),
        scale=Scale(status="scaled", m_per_unit=0.01),
        rooms=(
            Room(
                page=1,
                id="r1",
                type="kitchen",
                label="Küche",
                box=KITCHEN,
                area_m2=30.0,
                attrs={"number": "1.01"},
                apartment=flat,
            ),
            Room(
                page=1,
                id="r2",
                type="bathroom",
                label=second,
                box=BATH,
                area_m2=8.0,
                attrs={"number": "1.02"},
                apartment=flat,
            ),
        ),
        apartments=() if flat is None else (Apartment(id=flat, label="A", area_m2=flat_m2),),
    )


class Store:
    """Just what `takeoff_rows` asks of the ingest and the review store."""

    def __init__(self, state: ReviewState, shown: Drawing) -> None:
        self.state, self.shown = state, shown

    def drawing(self, drawing_id: str) -> Drawing:
        return self.shown

    def get(self, project: str | None, drawing_id: str) -> ReviewState:
        return self.state

    def update(
        self, project: str | None, drawing_id: str, change: Callable[[ReviewState], ReviewState]
    ) -> None:
        self.state = change(self.state)


def settled(shown: Drawing, *values: tuple[str, float | None]) -> dict[str, float]:
    """The rows' values after each step: (key, value) settles it as the surveyor's Settle stores
    it; (key, None) signs it off at the value the rows show, as POST .../signoff does."""
    state, quantities = ReviewState(), known_quantities(shown)
    for key, value in values:
        found = quantities[key]
        if value is None:
            seen = with_rejected_items(state, quantities)
            state = sign(state, found, shown, "QA describe", AT, shown=seen)
            continue
        state = apply(state, Edit(quantity=key, action="settle", value=value), found, shown, AT)
    store: Any = Store(state, shown)
    rows = takeoff_rows("d1", store, store, zeros=True).quantities
    return {found.key: found.value for found in rows}


def test_a_room_settled_on_its_number_row_is_that_area_on_every_row_of_the_room() -> None:
    rows = settled(drawing(), ("area:room|name=1.01", 22.4))
    for key in ("area:room|name=1.01", "area:room|name=küche", "area:room|label=küche",
                "area:room|label=küche|largest", "area:room:kitchen|largest"):  # fmt: skip
        assert rows[key] == 22.4, key
    for key in ("area:room", "area:room|indoor"):  # the sums the takeoff adds it into
        assert rows[key] == 30.4, key
    assert rows["area:apartment"] == 38.0  # an apartment's area is never derived (review-718)
    assert rows["area:room|label=bad"] == 8.0  # the other room is untouched


def test_a_sum_settled_by_a_person_or_not_adding_its_rooms_keeps_its_value() -> None:
    rows = settled(drawing(), ("area:room|indoor", 40.0), ("area:room|name=1.01", 22.4))
    assert rows["area:room|indoor"] == 40.0  # the person's own value for the sum
    assert rows["area:room"] == 30.4
    flat = settled(drawing(flat_m2=35.0), ("area:room|name=1.01", 22.4))
    assert flat["area:apartment|apartment=a"] == 35.0  # its own area, not 30 + 8
    assert flat["area:room|indoor"] == 30.4


def test_a_signed_off_sum_keeps_the_value_signed_review_718() -> None:
    rows = settled(drawing(), ("area:room|indoor", None), ("area:room|name=1.01", 22.4))
    assert rows["area:room|indoor"] == 38.0  # signed at 38 before the kitchen was settled
    assert rows["area:room"] == 30.4
    rows = settled(drawing(), ("area:room|name=1.01", 22.4), ("area:room|indoor", None),
                   ("area:room|name=1.01", 20.0))  # fmt: skip
    assert rows["area:room|indoor"] == 30.4  # signed at 30.4, then the kitchen settled again
    assert rows["area:room"] == 28.0


def test_a_printed_apartment_area_equal_to_its_rooms_sum_is_kept_review_718() -> None:
    rows = settled(drawing(flat_m2=38.0), ("area:room|name=1.01", 22.4))
    assert rows["area:apartment|apartment=a"] == 38.0  # printed 38 = 30 + 8 by chance
    assert rows["area:room|indoor"] == 30.4


def test_the_largest_of_two_rooms_does_not_take_one_rooms_settled_area() -> None:
    rows = settled(drawing(second="Küche"), ("area:room|name=1.01", 5.0))  # 30 -> 5, other is 8
    assert rows["area:room|label=küche|largest"] == 30.0  # as read: not 5, which is not largest
    assert rows["area:room|label=küche"] == 13.0  # the two rooms' sum takes it
    assert rows["area:room|name=1.01"] == 5.0
