"""The drawing model: field checks, the extraction_v1 names, and the marks per count key."""

import pytest
from pydantic import ValidationError

from app.core.drawing.model import (
    COUNT_KEYS,
    Drawing,
    Element,
    Mark,
    Page,
    Plan,
    Room,
    Scale,
)

PAGE = Page(page=1, width=100, height=50, unit="px")
BOX = (0.1, 0.2, 0.3, 0.4)


def test_element_reads_and_writes_the_format_name_class() -> None:
    by_field = Element(id="e1", class_="door", page=1, box=BOX)
    by_format = Element.model_validate({"id": "e1", "class": "door", "page": 1, "box": BOX})
    assert by_field == by_format
    assert by_field.model_dump(mode="json", by_alias=True)["class"] == "door"


def test_a_box_must_be_ordered_and_inside_the_page() -> None:
    assert Plan(id="p1", page=1, box=BOX).box == BOX
    with pytest.raises(ValidationError, match="x0 <= x1"):
        Plan(id="p1", page=1, box=(0.5, 0.2, 0.3, 0.4))
    with pytest.raises(ValidationError, match="less than or equal to 1"):
        Plan(id="p1", page=1, box=(0.1, 0.2, 0.3, 1.4))


def test_an_unknown_field_is_refused() -> None:
    with pytest.raises(ValidationError, match="colour"):
        Scale.model_validate({"status": "no_scale", "colour": "red"})


def test_a_drawing_needs_a_page() -> None:
    with pytest.raises(ValidationError, match="pages"):
        Drawing(file="data/demo/a.png", pages=(), scale=Scale(status="no_scale"))


def test_marks_by_quantity_lists_every_key_and_where_each_item_is() -> None:
    drawing = Drawing(
        file="data/demo/a.png",
        pages=(PAGE,),
        scale=Scale(status="no_scale"),
        plans=(Plan(id="p1", page=1, box=(0.0, 0.0, 1.0, 1.0)),),
        elements=(
            Element(id="e1", class_="door", page=1, box=BOX),
            Element(id="e2", class_="door", page=1, box=(0.5, 0.5, 0.6, 0.6)),
            Element(id="e3", class_="window", page=1, box=(0.7, 0.7, 0.8, 0.8)),
        ),
        rooms=(Room(id="r1", type="bedroom", page=1, box=(0.2, 0.2, 0.9, 0.9)),),
    )
    marks = drawing.marks_by_quantity()
    assert tuple(marks) == COUNT_KEYS
    assert marks["door"] == (Mark(page=1, box=BOX), Mark(page=1, box=(0.5, 0.5, 0.6, 0.6)))
    assert {key: len(found) for key, found in marks.items() if found} == {
        "door": 2,
        "window": 1,
        "room:bedroom": 1,
        "plan": 1,
    }
