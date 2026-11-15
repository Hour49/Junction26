"""The areas a sheet prints in its rooms' labels check the sheet's scale (area-root, QA R3-B6/B1:
T4's photo got 0.0325 m/px from a printed ratio at a camera's dpi, ~23x too small in area, and
its areas went out "±17%"). When the rooms with a printed area (at least LABEL_SCALE_ROOMS)
put the sheet's scale more than LABEL_SCALE_RANGE off in area (their median), every area and
length measured at that scale is flagged, as a disputed bar is: an estimate, so Low and never
certified. Synthetic."""

import pytest
from test_printed_scale import PAGE, label_room

from app.core.drawing.model import Drawing, Room, Scale
from app.core.pipeline.rules import apply_rules
from app.core.pipeline.takeoff import LABEL_SCALE_RANGE, label_disputed, quantity_key, take_off

BOXES = ((0.1, 0.1, 0.2, 0.3), (0.3, 0.1, 0.4, 0.3), (0.5, 0.1, 0.6, 0.3), (0.7, 0.1, 0.8, 0.3))


def sheet(scale: Scale, factor: float, printed: int = 3) -> Drawing:
    """`printed` rooms whose label prints `factor` times their outline at `scale`, and one room
    measured at it. A box is 200 x 200 px on PAGE; its outline is the box over BOX_RATIO."""
    from app.core.pipeline.raster_scale import BOX_RATIO

    m = scale.m_per_unit or 0.0
    outline = 200 * 200 * m * m / BOX_RATIO
    rooms = [label_room(f"r{i}", BOXES[i], round(factor * outline, 2)) for i in range(printed)]
    rooms.append(
        Room(
            id="m",
            type="bedroom",
            page=1,
            box=BOXES[3],
            area_m2=round(outline, 2),
            area_status="estimated",
            area_source="geometry_x_scale",
        )  # fmt: skip
    )
    return Drawing(file="t4.jpg", pages=(PAGE,), scale=scale, rooms=tuple(rooms))


RATIO = Scale(status="scaled", m_per_unit=0.0325, evidence=("scale_text",), text='1/32" = 1\'-0"')
DOORS = Scale(status="estimated", m_per_unit=0.02, source="doors", uncertainty=0.158)


@pytest.mark.parametrize("scale", [RATIO, DOORS])
def test_printed_room_areas_far_from_the_scale_flag_every_measured_area(scale: Scale) -> None:
    drawing = sheet(scale, factor=23.0)  # T4: the printed ratio at the camera's dpi
    said = label_disputed(drawing)
    assert said is not None and "3 rooms" in said and "23" in said, said
    quantities = take_off(drawing, apply_rules(drawing.marks_by_quantity()))
    total = quantities[quantity_key("area", "room")]  # sums the measured room too
    assert total.estimate is not None and said in total.estimate, total.estimate
    flagged = [q for q in quantities.values() if q.unit in ("m2", "m") and q.estimate]
    assert all(said in (q.estimate or "") for q in flagged)  # no other wording wins


@pytest.mark.parametrize("factor", [1.0, 1.2, 1 / 1.2, LABEL_SCALE_RANGE * 0.98])
def test_printed_room_areas_that_agree_with_the_scale_flag_nothing(factor: float) -> None:
    assert label_disputed(sheet(RATIO, factor)) is None
    assert label_disputed(sheet(DOORS, factor)) is None


def test_fewer_than_three_printed_rooms_flag_nothing() -> None:
    assert label_disputed(sheet(RATIO, factor=23.0, printed=2)) is None


def test_no_scale_no_check() -> None:
    unscaled = sheet(RATIO, 23.0).model_copy(update={"scale": Scale(status="no_scale")})
    assert label_disputed(unscaled) is None
