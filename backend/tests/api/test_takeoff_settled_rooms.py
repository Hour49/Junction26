"""A room's area settled on its own row still read the old value on the room's other rows (big QA
R1 row 12, describe): flat-b's kitchen settled at 22.40 kept "area of room (label Küche) 30.00"
and "area of room (indoor) 53.00". Synthetic: a kitchen printed 30 m² and a bathroom of 8 m²."""

from collections.abc import Callable
from typing import Any

from app.api.takeoff import takeoff_rows
from app.core.drawing.model import Apartment, Drawing, Page, Room, Scale
from app.core.pipeline.takeoff import known_quantities
from app.core.review.model import Edit, ReviewState
from app.core.review.review import apply

AT = "2026-11-15T05:30:00Z"
KITCHEN, BATH = (0.1, 0.1, 0.5, 0.5), (0.5, 0.1, 0.7, 0.5)


def drawing(*, flat_m2: float | None = None) -> Drawing:
    """`flat_m2`: an apartment around both rooms whose own area is not their sum."""
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
                label="Bad",
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


def settled(shown: Drawing, *values: tuple[str, float]) -> dict[str, float]:
    """The rows' values after each (key, value) settle, as the surveyor's Settle stores it."""
    state = ReviewState()
    for key, value in values:
        found = known_quantities(shown)[key]
        state = apply(state, Edit(quantity=key, action="settle", value=value), found, shown, AT)
    store: Any = Store(state, shown)
    rows = takeoff_rows("d1", store, store, zeros=True).quantities
    return {found.key: found.value for found in rows}


def test_a_room_settled_on_its_number_row_is_that_area_on_every_row_of_the_room() -> None:
    rows = settled(drawing(), ("area:room|name=1.01", 22.4))
    for key in ("area:room|name=1.01", "area:room|name=küche", "area:room|label=küche",
                "area:room|label=küche|largest", "area:room:kitchen|largest"):  # fmt: skip
        assert rows[key] == 22.4, key
    for key in ("area:room", "area:room|indoor", "area:apartment"):  # sums that add it
        assert rows[key] == 30.4, key
    assert rows["area:room|label=bad"] == 8.0  # the other room is untouched


def test_a_sum_settled_by_a_person_or_not_adding_its_rooms_keeps_its_value() -> None:
    rows = settled(drawing(), ("area:room|indoor", 40.0), ("area:room|name=1.01", 22.4))
    assert rows["area:room|indoor"] == 40.0  # the person's own value for the sum
    assert rows["area:room"] == 30.4
    flat = settled(drawing(flat_m2=35.0), ("area:room|name=1.01", 22.4))
    assert flat["area:apartment|apartment=a"] == 35.0  # its own area, not 30 + 8
    assert flat["area:room|indoor"] == 30.4
