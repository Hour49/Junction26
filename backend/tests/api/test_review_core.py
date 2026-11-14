"""The review use cases on their own (app/core/review/review.py)."""

import pytest

from app.core.drawing.model import Drawing, Element, Mark, MeasuredValue, Page, Room, Scale
from app.core.errors import InvalidInputError
from app.core.pipeline.model import Quantity, QuantityConflict
from app.core.review.model import Edit, MethodValue, ReviewState
from app.core.review.review import NotAllowedError, apply, label, mark_views, row, sign

AT = "2026-11-14T01:00:00Z"
PAGE = Page(page=1, width=100, height=100, unit="pt")
BOX_A = (0.1, 0.1, 0.2, 0.2)
BOX_B = (0.3, 0.3, 0.4, 0.4)
DRAWING = Drawing(
    file="x.pdf",
    pages=(PAGE,),
    scale=Scale(status="no_scale"),
    rooms=(
        Room(id="r1", type="kitchen", label="Küche", page=1, box=BOX_A, area_m2=10.0),
        Room(id="r2", type="other", page=1, box=BOX_B, area_m2=None),
    ),
)


def quantity(
    key: str,
    value: float,
    unit: str,
    *boxes: tuple[float, float, float, float],
    conflict: QuantityConflict | None = None,
) -> Quantity:
    return Quantity.model_validate(
        {
            "key": key,
            "value": value,
            "unit": unit,
            "marks": [Mark(page=1, box=box) for box in boxes],
            "rule": "each-once",
            "conflict": conflict,
        }
    )


def disputed(resolved: bool) -> QuantityConflict:
    values = (
        MeasuredValue(value=2, method="parser"),
        MeasuredValue(value=3, method="ifc_model"),
    )
    rule = {"rule": "the sheet's own count", "value": 2} if resolved else None
    return QuantityConflict.model_validate({"values": values, "resolution": rule})


def test_a_count_without_marks_recounts_from_its_own_value() -> None:
    model_doors = quantity("door|model", 10, "count")  # a model's count: no marks on the sheet
    edit = Edit(quantity="door|model", action="add", page=1, box=BOX_A)
    state = apply(ReviewState(), edit, model_doors, DRAWING, AT)
    assert row(model_doors, DRAWING, state, {}).value == 11


def test_a_mark_is_named_by_the_room_it_marks() -> None:
    total = quantity("area:room", 30.0, "m2", BOX_A, BOX_B)
    first, second = mark_views(total, DRAWING, ReviewState())
    assert (first.label, first.ref, first.value) == ("Küche", "r1", 10.0)
    assert (second.label, second.value) == ("other", None)  # no printed label: the room type


def test_a_sum_with_a_room_of_unknown_area_is_not_recounted() -> None:
    total = quantity("area:room", 30.0, "m2", BOX_A, BOX_B)
    edit = Edit(quantity="area:room", action="reject", mark="m1")
    assert row(total, DRAWING, apply(ReviewState(), edit, total, DRAWING, AT), {}).value == 20.0
    edit = Edit(quantity="area:room", action="reject", mark="m2")
    state = apply(ReviewState(), edit, total, DRAWING, AT)
    assert row(total, DRAWING, state, {}).value == 30.0  # only settle can change it now


def test_marks_are_added_to_counts_only() -> None:
    total = quantity("area:room", 30.0, "m2", BOX_A)
    with pytest.raises(InvalidInputError, match="counts only"):
        edit = Edit(quantity="area:room", action="add", page=1, box=BOX_B)
        apply(ReviewState(), edit, total, DRAWING, AT)


def test_a_conflict_no_rule_decides_is_settled_before_sign_off() -> None:
    doors = quantity("door", 2, "count", BOX_A, BOX_B, conflict=disputed(resolved=False))
    shown = row(doors, DRAWING, ReviewState(), {})
    assert (shown.status, shown.needs_person) == ("conflict", True)
    assert shown.first is not None and shown.second is not None
    assert (shown.first.value, shown.second.value) == (2, 3)
    with pytest.raises(NotAllowedError, match="settle"):
        sign(ReviewState(), doors, DRAWING, "Ana", AT)
    state = apply(
        ReviewState(), Edit(quantity="door", action="settle", value=3), doors, DRAWING, AT
    )
    state = sign(state, doors, DRAWING, "Ana", AT)
    assert state.signed["door"].value == 3


def test_a_conflict_a_rule_decided_can_be_signed_off() -> None:
    doors = quantity("door", 2, "count", BOX_A, BOX_B, conflict=disputed(resolved=True))
    assert row(doors, DRAWING, ReviewState(), {}).needs_person is False
    assert sign(ReviewState(), doors, DRAWING, "Ana", AT).signed["door"].value == 2


def test_a_signed_quantity_is_locked_until_reset() -> None:
    doors = quantity("door", 2, "count", BOX_A, BOX_B)
    state = sign(ReviewState(), doors, DRAWING, "Ana", AT)
    with pytest.raises(NotAllowedError, match="signed off by Ana"):
        apply(state, Edit(quantity="door", action="settle", value=3), doors, DRAWING, AT)
    state = apply(state, Edit(quantity="door", action="reset"), doors, DRAWING, AT)
    assert state == ReviewState()


@pytest.mark.parametrize(
    ("key", "text"),
    [
        ("door", "door count"),
        ("room:sauna", "room sauna count"),
        ("area:room|indoor", "area of room (indoor)"),
        ("length:room|name=küche|storey=level 1", "length of room (name küche, storey level 1)"),
    ],
)
def test_a_key_reads_as_a_label(key: str, text: str) -> None:
    assert label(key) == text


def test_two_methods_that_agree_show_as_agree_with_both_values() -> None:
    values = (MeasuredValue(value=2, method="parser"), MeasuredValue(value=2, method="ifc_model"))
    agreed = QuantityConflict(values=values, resolution=None, status="agree")
    doors = quantity("door", 2, "count", BOX_A, BOX_B).model_copy(update={"agree": agreed})
    shown = row(doors, DRAWING, ReviewState(), {})
    assert shown.status == "agree"
    assert (shown.first, shown.second) == (
        MethodValue(method="parser", value=2),
        MethodValue(method="ifc_model", value=2),
    )
    assert shown.conflict is None


def test_a_second_reader_s_unlocated_marks_are_counted_but_never_drawn() -> None:
    plan = (0.0, 0.0, 1.0, 1.0)  # decide's count swap gives an added element the plan's box
    seen = (0.5, 0.5, 0.6, 0.6)
    drawing = DRAWING.model_copy(
        update={
            "elements": (
                Element(id="t1", class_="toilet", page=1, box=seen),
                Element(id="d1", class_="toilet", page=1, box=plan, attrs={"located": False}),
                Element(id="d2", class_="toilet", page=1, box=plan, attrs={"located": False}),
            )
        }
    )
    toilets = quantity("toilet", 3, "count", seen, plan, plan)
    shown = row(toilets, drawing, ReviewState(), {})
    assert [(mark.id, mark.n, mark.ref) for mark in shown.marks] == [("m1", 1, "t1")]
    assert (shown.value, shown.unlocated) == (3, {"toilet": 2})
    edit = Edit(quantity="toilet", action="reject", mark="m1")
    assert row(toilets, drawing, apply(ReviewState(), edit, toilets, drawing, AT), {}).value == 2
