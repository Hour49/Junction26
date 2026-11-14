"""floor_plans: a plan box with no labelled room is not a floor plan when another box on the page
has one (an elevation or a section beside the plans). Synthetic boxes."""

from test_raster_composite import FILE, SHEET, Fake

from app.adapters.raster import assemble, parse_components
from app.core.drawing.model import Box, Element, Plan, Room
from app.core.pipeline.plan_rooms import floor_plans

UPPER: Box = (0.10, 0.50, 0.75, 0.68)
GROUND: Box = (0.20, 0.72, 0.80, 0.88)
FACADE: Box = (0.09, 0.08, 0.57, 0.25)
SIDE: Box = (0.67, 0.09, 0.92, 0.25)


def plan(box: Box, page: int = 1) -> Plan:
    return Plan(id="x", page=page, box=box)


def room(box: Box, label: str | None = "HUONE", page: int = 1) -> Room:
    return Room(id="x", type="other", label=label, page=page, box=box)


IN_UPPER = room((0.27, 0.52, 0.37, 0.66))
IN_GROUND = room((0.27, 0.72, 0.37, 0.82), "KEITTIÖ")


def test_a_box_without_a_labelled_room_beside_plans_that_have_them_is_not_a_floor_plan() -> None:
    plans = [plan(FACADE), plan(UPPER), plan(GROUND), plan(SIDE)]
    assert floor_plans(plans, [IN_UPPER, IN_GROUND]) == (plans[1], plans[2])


def test_a_plan_whose_room_labels_were_not_read_stays_beside_a_labelled_one() -> None:
    """review-377: two real plans side by side, labels read only in the first."""
    plans = [plan(UPPER), plan(GROUND), plan(FACADE)]
    unread = room((0.27, 0.72, 0.37, 0.82), None)
    assert floor_plans(plans, [IN_UPPER, unread]) == (plans[0], plans[1])


def test_a_sheet_whose_rooms_carry_no_label_keeps_every_plan_box() -> None:
    plans = [plan(UPPER), plan(GROUND)]
    unlabelled = [room((0.27, 0.52, 0.37, 0.66), None), room((0.27, 0.72, 0.37, 0.82), "  ")]
    assert floor_plans(plans, unlabelled) == tuple(plans)
    assert floor_plans(plans, []) == tuple(plans)


def test_each_page_is_judged_by_its_own_rooms() -> None:
    plans = [plan(UPPER), plan(FACADE), plan(GROUND, page=2), plan(FACADE, page=2)]
    assert floor_plans(plans, [IN_UPPER]) == (plans[0], plans[2], plans[3])
    other_page = room((0.27, 0.52, 0.37, 0.66), page=2)  # inside UPPER's box, on page 2
    assert floor_plans([plan(UPPER), plan(FACADE)], [other_page]) == (plan(UPPER), plan(FACADE))


def test_the_composite_numbers_only_the_floor_plans_and_keeps_what_an_elevation_held() -> None:
    door = Element.model_validate(
        {"id": "x", "class": "door", "page": 1, "box": (0.2, 0.1, 0.3, 0.2)}
    )
    readers = {
        "det": Fake(plans=[plan(FACADE), plan(UPPER), plan(GROUND), plan(SIDE)], elements=[door]),
        "ocr": Fake(rooms=[IN_UPPER, IN_GROUND], read=["room"]),
    }
    parts = parse_components("elements=det,plans=det,rooms=ocr")
    found = assemble(parts, readers.__getitem__).extract(FILE, SHEET)
    assert [(p.id, p.box) for p in found.plans] == [("p1", UPPER), ("p2", GROUND)]
    assert [r.plan for r in found.rooms] == ["p1", "p2"]
    assert [(e.class_, e.plan) for e in found.elements] == [("door", None)]  # on the facade
    assert (
        "raster composite: 2 of 4 plan boxes hold no room beside ones with labelled rooms: not "
        "floor plans"
    ) in found.notes


def test_the_composite_keeps_every_plan_box_when_no_rooms_source_is_given() -> None:
    readers = {"det": Fake(plans=[plan(FACADE), plan(UPPER)])}
    found = assemble(parse_components("plans=det"), readers.__getitem__).extract(FILE, SHEET)
    assert [p.box for p in found.plans] == [FACADE, UPPER]
    assert not any("plan boxes" in note for note in found.notes)
