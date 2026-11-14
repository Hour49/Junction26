"""A drawing's takeoff builds its room-name tables once, not once per row (cold GET of a big
project: 13,396 rows x every room made /api/projects/{id} take 7.8 s the first time)."""

from typing import Any

import pytest

from app.api import takeoff as takeoff_api
from app.api.takeoff import takeoff_rows
from app.core.drawing.model import Drawing, Page, Room, RoomType, Scale
from app.core.pipeline.takeoff import known_quantities
from app.core.review import review
from app.core.review.ask import RULES
from app.core.review.model import ReviewState
from app.core.review.review import room_names_of, row

BOX = (0.1, 0.1, 0.2, 0.2)
KINDS: tuple[RoomType, ...] = ("kitchen", "bedroom", "bathroom", "other", "other", "other")
LABELS = ("Küche", "MH1", "WC 1.03", "Rum", "Hall\n1.05", "Tekn. tila")


def drawing() -> Drawing:
    rooms = tuple(
        Room(id=f"r{n}", type=kind, label=label, page=1, box=BOX, area_m2=4.0 + n)
        for n, (kind, label) in enumerate(zip(KINDS, LABELS, strict=True), 1)
    )
    return Drawing(
        file="x.pdf",
        pages=(Page(page=1, width=100, height=100, unit="pt"),),
        scale=Scale(status="scaled", m_per_unit=0.01),
        rooms=rooms,
    )


class Store:
    """Just what `takeoff_rows` asks of the ingest and the review store."""

    def drawing(self, drawing_id: str) -> Drawing:
        return drawing()

    def get(self, project: str | None, drawing_id: str) -> ReviewState:
        return ReviewState()


def test_the_room_name_tables_are_built_once_per_drawing_not_once_per_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    built: dict[str, int] = {"printed": 0, "labelled": 0}
    printed, labelled = review._printed_names, review._room_labels  # pyright: ignore[reportPrivateUsage]

    def count_printed(found: Drawing) -> dict[str, str]:
        built["printed"] += 1
        return printed(found)

    def count_labelled(found: Drawing) -> dict[str, str]:
        built["labelled"] += 1
        return labelled(found)

    monkeypatch.setattr(review, "_printed_names", count_printed)
    monkeypatch.setattr(review, "_room_labels", count_labelled)
    store: Any = Store()
    got = takeoff_rows("d1", store, store, zeros=True)
    filtered = [found for found in got.quantities if "name=" in found.key]
    assert len(filtered) >= 6  # a row per room and measure: the tables serve all of them
    assert built == {"printed": 1, "labelled": 1}
    assert takeoff_api.room_names_of is review.room_names_of


def test_a_row_reads_the_same_with_the_tables_given_or_built() -> None:
    found = drawing()
    names = room_names_of(found)
    for quantity in known_quantities(found).values():
        alone = row(quantity, found, ReviewState(), RULES)
        shared = row(quantity, found, ReviewState(), RULES, names)
        assert alone.model_dump_json() == shared.model_dump_json(), quantity.key
