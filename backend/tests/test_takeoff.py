"""Stages 9-10 beyond plain counts: the counting rules as data, areas, lengths and volumes, and
the filters (label, name, apartment, storey) a query looks a quantity up by."""

import re

from app.core.answering.model import Query
from app.core.drawing.model import (
    Apartment,
    Conflict,
    Drawing,
    Element,
    Mark,
    MeasuredValue,
    ModelObject,
    Page,
    Plan,
    Resolution,
    Room,
    Scale,
    Subject,
)
from app.core.pipeline import rules
from app.core.pipeline.model import CountingRule
from app.core.pipeline.rules import (
    APARTMENT_AREA,
    ELEMENT_QUANTITY,
    INDOOR_TOTAL,
    SAUNA_ROOM_ELSE_STOVE,
    SHOWERS_AND_BATHTUBS,
)
from app.core.pipeline.takeoff import known_quantities

BOX = (0.1, 0.1, 0.2, 0.2)
PAGE = Page(page=1, width=100, height=100, unit="pt")


def element(n: int, cls: str, **attrs: str | float) -> Element:
    return Element.model_validate(
        {"id": f"e{n}", "class": cls, "page": 1, "box": BOX, "plan": "p1", "attrs": attrs}
    )


def room(n: int, kind: str, area: float | None, **fields: object) -> Room:
    return Room.model_validate(
        {"id": f"r{n}", "type": kind, "page": 1, "box": BOX, "area_m2": area, **fields}
    )


def drawing(**fields: object) -> Drawing:
    return Drawing.model_validate(
        {"file": "data/demo/a.pdf", "pages": (PAGE,), "scale": Scale(status="no_scale"), **fields}
    )


def value(quantities: dict, query: Query) -> int | float | None:
    found = quantities.get(query.key())
    return None if found is None else found.value


def test_saunas_count_sauna_rooms_else_stoves() -> None:
    stoves = known_quantities(drawing(elements=(element(1, "sauna_stove"),)))
    assert value(stoves, Query(subject="sauna")) == 1
    assert stoves[Query(subject="sauna").key()].rule == SAUNA_ROOM_ELSE_STOVE.id
    both = drawing(
        elements=(element(1, "sauna_stove"), element(2, "sauna_stove")),
        rooms=(room(1, "sauna", None),),
    )
    assert value(known_quantities(both), Query(subject="sauna")) == 1


def test_saunas_fall_back_to_stoves_when_rooms_were_not_read() -> None:
    """A detector reads stoves but no rooms: the sauna count is its stoves, on the sheet and
    per storey. Rooms read without stoves stay unknown (a sheet without sauna rooms would count
    stoves nobody looked for); both read keep room-else-stove."""
    items = {
        "plans": (Plan(id="p1", page=1, box=BOX, storey="EG"),),
        "elements": (element(1, "sauna_stove"), element(2, "sauna_stove"), element(3, "door")),
    }
    detector = known_quantities(drawing(read=["sauna_stove", "door"], **items))
    assert value(detector, Query(subject="sauna")) == 2
    assert detector[Query(subject="sauna").key()].rule == SAUNA_ROOM_ELSE_STOVE.id
    assert value(detector, Query(subject="sauna", storey="EG")) == 2
    assert Query(subject="room:sauna").key() not in detector
    none_found = known_quantities(drawing(read=["sauna_stove"], plans=items["plans"]))
    assert value(none_found, Query(subject="sauna")) == 0
    rooms_only = known_quantities(drawing(read=["room"], **items))
    assert Query(subject="sauna").key() not in rooms_only
    both = known_quantities(
        drawing(read=["sauna_stove", "room"], rooms=(room(1, "sauna", None, plan="p1"),), **items)
    )
    assert value(both, Query(subject="sauna")) == 1


def test_showers_and_bathtubs_add_up() -> None:
    found = known_quantities(
        drawing(elements=(element(1, "shower"), element(2, "bathtub"), element(3, "bathtub")))
    )
    combined = found[Query(subject="shower+bathtub").key()]
    assert (combined.value, combined.rule, len(combined.marks)) == (3, SHOWERS_AND_BATHTUBS.id, 3)
    assert value(found, Query(subject="shower")) == 1


def test_stated_totals_give_a_combined_count_only_when_its_parts_are_stated() -> None:
    assert value(known_quantities(drawing(counts={"shower": 2, "bathtub": 1})), Query(
        subject="shower+bathtub"
    )) == 3  # fmt: skip
    assert Query(subject="shower+bathtub").key() not in known_quantities(
        drawing(counts={"shower": 2})
    )
    assert value(known_quantities(drawing(counts={"room:sauna": 1})), Query(subject="sauna")) == 1


ROOMS = (
    room(1, "other", 12.5, label="Zimmer", apartment="aA", attrs={"number": "1.01"}),
    room(2, "other", 10.0, label="Zimmer", apartment="aA", attrs={"number": "1.02"}),
    room(3, "balcony", 6.0, label="Balkon", apartment="aA", outdoor=True),
    room(4, "shaft", 2.0, label="Lift", apartment="aA"),
    room(5, "kitchen", 8.25, label="Küche", apartment="aB", attrs={"number": "2.01"}),
)


def test_room_areas_by_number_label_and_indoor_total() -> None:
    found = known_quantities(drawing(rooms=ROOMS))
    assert value(found, Query(measure="area", subject="room", name="1.02")) == 10.0
    assert value(found, Query(measure="area", subject="room", label="zimmer")) == 22.5
    assert value(found, Query(subject="room", label="Zimmer")) == 2
    indoor = found[Query(measure="area", subject="room", indoor=True).key()]
    assert (indoor.value, indoor.unit, indoor.rule) == (32.75, "m2", INDOOR_TOTAL.id)
    assert Query(measure="area", subject="room", name="Zimmer").key() not in found  # shared name


def test_a_total_with_a_room_of_unknown_area_is_unknown() -> None:
    found = known_quantities(drawing(rooms=(*ROOMS, room(6, "hall", None, label="Flur"))))
    assert Query(measure="area", subject="room", indoor=True).key() not in found
    assert value(found, Query(measure="area", subject="room", label="Zimmer")) == 22.5


def test_apartment_area_is_stated_else_its_indoor_rooms_without_shafts() -> None:
    apartments = (Apartment(id="aA", label="A"), Apartment(id="aB", label="B", area_m2=9.0))
    found = known_quantities(drawing(rooms=ROOMS, apartments=apartments))
    a = found[Query(measure="area", subject="apartment", apartment="A").key()]
    assert (a.value, a.rule) == (22.5, APARTMENT_AREA.id)
    assert value(found, Query(measure="area", subject="apartment", apartment="B")) == 9.0
    assert value(found, Query(subject="apartment")) == 2


IFC_ROOM = {"number": "0.04", "ifc_name": "0.04", "ifc_long_name": "Office", "storey": "EG"}


def test_storey_filters_use_each_item_s_own_storey_else_its_plan_s() -> None:
    found = known_quantities(
        drawing(
            plans=(Plan(id="p1", page=1, box=BOX, storey="EG"),),
            elements=(
                element(1, "door"),
                element(2, "door", storey="OG"),  # drawn on the EG sheet, belongs to OG
                element(3, "wall", storey="EG", length_m=4.0, net_volume_m3=1.2),
                element(4, "wall", length_m=2.5, net_volume_m3=0.8),
            ),
            rooms=(room(1, "other", 20.0, label="Office 0.04", plan="p1", attrs=IFC_ROOM),),
        )
    )
    assert value(found, Query(subject="door", storey="EG")) == 1
    assert value(found, Query(subject="door", storey="og")) == 1
    # The sheet counts what it draws of its own storey, as stage 8 does (R2-qa-1-1); the OG door
    # is left out of it, with the reason, and counted on OG.
    door = found[Query(subject="door").key()]
    assert (door.value, [why for _, why in door.excluded]) == (
        1,
        ["on storey OG in the building model, seen through the cut"],
    )
    length = found[Query(measure="length", subject="wall", storey="EG").key()]
    assert (length.value, length.unit, length.rule) == (6.5, "m", ELEMENT_QUANTITY.id)
    assert value(found, Query(measure="volume", subject="wall", storey="EG")) == 2.0
    for name in ("Office (0.04)", "0.04", "Office 0.04", "office"):
        query = Query(measure="area", subject="room", name=name, storey="EG")
        assert value(found, query) == 20.0
    assert value(found, Query(measure="area", subject="room", storey="EG")) == 20.0
    assert value(found, Query(subject="room", storey="EG")) == 1


def test_a_room_is_found_by_the_name_and_number_a_sheet_prints() -> None:
    # The vector extractor's room: no IFC attrs, the storey from the sheet's plan.
    printed = {"number": "67-1", "name": "ELUTUBA+KÖÖK"}
    found = known_quantities(
        drawing(
            plans=(Plan(id="p1", page=1, box=BOX, storey="5.korrus"),),
            rooms=(room(1, "other", 25.247, label="ELUTUBA+KÖÖK 67-1", plan="p1", attrs=printed),),
        )
    )
    for name in ("ELUTUBA+KÖÖK (67-1)", "67-1", "elutuba+köök 67-1", "ELUTUBA+KÖÖK"):
        query = Query(measure="area", subject="room", name=name, storey="5.korrus")
        assert value(found, query) == 25.247


def test_an_element_quantity_one_element_lacks_is_unknown_and_the_model_is_never_a_sheet() -> None:
    found = known_quantities(
        drawing(elements=(element(1, "wall", length_m=3.0), element(2, "wall")))
    )
    assert Query(measure="length", subject="wall").key() not in found
    assert value(found, Query(subject="wall")) == 2
    assert Query(subject="wall", model=True).key() not in found


def test_areas_and_lengths_on_an_estimated_or_not_to_scale_sheet_say_what_they_rest_on() -> None:
    items = {
        "rooms": (room(1, "living", 16.7, label="OH"),),
        "elements": (element(1, "wall", length_m=3.0, net_volume_m3=0.5),),
    }
    estimated = Scale(status="estimated", m_per_unit=0.02, source="door widths", uncertainty=0.15)
    found = known_quantities(drawing(scale=estimated, **items))
    area = found[Query(measure="area", subject="room", label="OH").key()]
    assert area.estimate == (
        "measured on an estimated scale (door widths), which may be off by about ±15%"
    )
    assert found[Query(measure="length", subject="wall").key()].estimate == area.estimate
    assert found[Query(measure="volume", subject="wall").key()].estimate is None
    assert found[Query(subject="room").key()].estimate is None  # a count needs no scale
    unscaled = known_quantities(
        drawing(scale=Scale(status="not_to_scale", evidence=("not_to_scale_note",)), **items)
    )
    assert "not to scale" in str(unscaled[Query(measure="area", subject="room").key()].estimate)
    scaled = known_quantities(
        drawing(scale=Scale(status="scaled", m_per_unit=0.01, evidence=("scale_text",)), **items)
    )
    assert scaled[Query(measure="area", subject="room").key()].estimate is None


def test_a_class_the_extraction_did_not_read_has_no_count_and_none_means_all_read() -> None:
    """None: everything was read (gold). []: nothing was, so not even the plan count (a raster
    extractor that read nothing answered 0 floors on every CubiCasa sheet). A read list keeps
    plans and apartments, which need no class."""
    items = {
        "plans": (Plan(id="p1", page=1, box=BOX, storey="EG"),),
        "elements": (element(1, "door"), element(2, "window"), element(3, "wall", length_m=2.0)),
        "rooms": (room(1, "sauna", 4.0, plan="p1"),),
    }
    nothing = known_quantities(drawing(read=[], **items))
    assert Query(subject="window").key() not in nothing
    assert Query(subject="room:sauna").key() not in nothing
    assert Query(subject="door", storey="EG").key() not in nothing
    assert Query(measure="area", subject="room").key() not in nothing
    assert nothing == {}  # nothing read: not even the plans, which are not a class
    everything = known_quantities(drawing(read=None, **items))
    assert value(everything, Query(subject="window")) == 1
    doors = known_quantities(drawing(read=["door", "room"], **items))
    assert value(doors, Query(subject="door")) == 1
    assert value(doors, Query(subject="room:sauna")) == 1
    assert Query(subject="window").key() not in doors
    assert Query(measure="length", subject="wall").key() not in doors
    assert Query(subject="sauna").key() not in doors  # room else stove: the stoves were not read
    assert value(doors, Query(subject="plan")) == 1  # something was read: its plans count
    stated = known_quantities(drawing(counts={"window": 3, "door": 2}, read=["door"]))
    assert (value(stated, Query(subject="door")), Query(subject="window").key() in stated) == (
        2,
        False,
    )


def test_a_room_area_sum_is_an_estimate_when_one_of_its_rooms_is_estimated() -> None:
    estimated = {"area_status": "estimated", "area_source": "geometry_x_estimate"}
    rooms = (
        room(1, "living", 16.7, label="OH", **estimated, area_uncertainty=0.35),
        room(2, "kitchen", 9.4, label="K", area_status="exact", area_source="printed"),
    )
    scaled = Scale(status="scaled", m_per_unit=0.01, evidence=("scale_text",))
    found = known_quantities(drawing(scale=scaled, rooms=rooms))
    total = found[Query(measure="area", subject="room").key()]
    assert (
        total.estimate
        == "1 of 2 room areas is measured on an estimated scale; the area may be off by about ±35%"
    )
    assert found[Query(measure="area", subject="room", name="K").key()].estimate is None
    # a printed (exact) area does not rest on the sheet's estimated scale; an unset one does
    guessed = Scale(status="estimated", m_per_unit=0.02, source="door widths")
    on_guess = known_quantities(drawing(scale=guessed, rooms=rooms))
    assert on_guess[Query(measure="area", subject="room", name="K").key()].estimate is None
    # an outline at an estimated scale also says how that scale was estimated
    assert on_guess[Query(measure="area", subject="room").key()].estimate == (
        "1 of 2 room areas is measured on an estimated scale (door widths); "
        "the area may be off by about ±35%"
    )
    unset = known_quantities(drawing(scale=guessed, rooms=(room(3, "hall", 5.0, label="ET"),)))
    assert unset[Query(measure="area", subject="room").key()].estimate == (
        "measured on an estimated scale (door widths)"
    )


def _room_count_entry(drawn: int, own: int, picked: int | None) -> dict[str, object]:
    return {
        "id": "c1",
        "quantity": "room_count",
        "subject": {"kind": "sheet", "ref": None},
        "status": "conflict",
        "tolerance": 0,
        "values": [
            {"value": drawn, "unit": "rooms", "method": "plan_drawing", "page": 1, "box": BOX},
            {"value": own, "unit": "rooms", "method": "ifc_model", "page": 1, "box": OTHER},
        ],
        "resolution": None if picked is None else {"rule": "keep the storey's", "value": picked},
    }


OTHER = (0.5, 0.5, 0.6, 0.6)


def test_a_disputed_room_set_disputes_the_storey_s_area_total_the_same_way() -> None:
    """The sheet draws 3 rooms, 2 of them on its own storey 0: the count's two values are those
    two sets, so the area total carries each set's sum and the rule's pick, even when the room
    only one set has is small (1.6% here, under the 2% of two measurements)."""
    sheet = drawing(
        plans=(Plan(id="p1", page=1, box=BOX, storey="0"),),
        rooms=(
            room(1, "other", 10.0, plan="p1"),
            room(2, "other", 20.0, plan="p1"),
            room(3, "other", 0.5, plan="p1", attrs={"storey": "-1"}),
        ),
        conflicts=(_room_count_entry(3, 2, picked=2),),
    )
    found = known_quantities(sheet)
    area = found[Query(measure="area", subject="room", storey="0").key()]
    assert area.value == 30.0
    assert area.conflict is not None and area.conflict.resolution is not None
    assert [(v.value, v.unit, v.method) for v in area.conflict.values] == [
        (30.5, "m2", "plan_drawing"),
        (30.0, "m2", "ifc_model"),
    ]
    assert area.conflict.resolution.value == 30.0 and area.conflict.derived is not None
    whole = found[Query(subject="room").key()]  # the sheet counted 3; the rule keeps 2
    assert (whole.value, [m.box for m in whole.marks]) == (2, [OTHER])
    sheet_area = found[Query(measure="area", subject="room").key()]
    assert sheet_area.value == 30.0
    assert found[Query(subject="room", storey="-1").key()].conflict is None  # not the sheet's


def test_with_a_model_the_storey_s_disputed_total_is_summed_from_the_model_like_its_value() -> None:
    """The model states 10.0 and 20.0 for the storey's two spaces; the sheet's outlines measure
    them 10.001 and 20.0, so summing outlines would give 30.001, which is not the key's 30.0.
    The drawn set keeps its outlines: the space of storey -1 shows 0.5 of its 9.0."""
    spaces = (
        model_object(1, "space", "0", "r1", area_m2=10.0, name="0.01"),
        model_object(2, "space", "0", "r2", area_m2=20.0, name="0.02"),
        model_object(3, "space", "-1", "r3", area_m2=9.0, name="-1.01"),
    )
    sheet = drawing(
        plans=(Plan(id="p1", page=1, box=BOX, storey="0"),),
        rooms=(
            room(1, "other", 10.001, plan="p1"),
            room(2, "other", 20.0, plan="p1"),
            room(3, "other", 0.5, plan="p1", attrs={"storey": "-1"}),
        ),
        conflicts=(_room_count_entry(3, 2, picked=2),),
        model_objects=spaces,
    )
    area = known_quantities(sheet)[Query(measure="area", subject="room", storey="0").key()]
    assert area.value == 30.0
    assert area.conflict is not None and area.conflict.resolution is not None
    assert [v.value for v in area.conflict.values] == [30.501, 30.0]
    assert area.conflict.resolution.value == 30.0
    assert area.conflict.derived is not None and "in the model" in area.conflict.derived


def test_a_conflict_entry_is_attached_only_to_a_quantity_whose_value_it_lists() -> None:
    sheet = drawing(
        plans=(Plan(id="p1", page=1, box=BOX, storey="0"),),
        rooms=(room(1, "other", 10.0, plan="p1"), room(2, "other", 20.0, plan="p1")),
        conflicts=(_room_count_entry(4, 3, picked=3),),  # measured something else than 2 rooms
    )
    found = known_quantities(sheet)
    assert found[Query(subject="room").key()].value == 2
    assert all(quantity.conflict is None for quantity in found.values())


def test_a_room_area_conflict_is_on_that_room_s_area_by_any_of_its_names() -> None:
    entry = {
        "id": "c1",
        "quantity": "room_area",
        "subject": {"kind": "room", "ref": "r1"},
        "status": "conflict",
        "tolerance": 0.02,
        "values": [
            {"value": 12.5, "unit": "m2", "method": "printed_label", "page": 1, "box": BOX},
            {"value": 13.4, "unit": "m2", "method": "polygon_x_scale", "page": 1, "box": BOX},
        ],
        "resolution": {"rule": "the printed label over the outline", "value": 12.5},
    }
    sheet = drawing(
        rooms=(room(1, "bedroom", 12.5, label="MH", attrs={"number": "2.01"}),),
        conflicts=(entry,),
    )
    found = known_quantities(sheet)
    for name in ("MH", "2.01"):
        quantity = found[Query(measure="area", subject="room", name=name).key()]
        assert quantity.value == 12.5 and quantity.conflict is not None


def test_the_largest_room_of_a_label_or_a_type() -> None:
    sheet = drawing(
        rooms=(
            room(1, "bedroom", 11.57, label="MH"),
            room(2, "bedroom", 9.0, label="MH"),
            room(3, "bedroom", 12.0, label="MH 3"),
        )
    )
    found = known_quantities(sheet)
    by_label = Query(measure="area", subject="room", label="MH", largest=True)
    assert value(found, by_label) == 11.57
    assert value(found, Query(measure="area", subject="room:bedroom", largest=True)) == 12.0
    unknown = drawing(rooms=(room(1, "bedroom", 11.0, label="MH"), room(2, "bedroom", None)))
    assert value(known_quantities(unknown), by_label) == 11.0
    largest_bedroom = Query(measure="area", subject="room:bedroom", largest=True)
    assert value(known_quantities(unknown), largest_bedroom) is None  # one area unknown


def test_a_rectangular_room_s_longer_side_at_the_sheet_s_scale() -> None:
    rectangle = ((0.1, 0.1), (0.5, 0.1), (0.5, 0.3), (0.1, 0.3))  # 40 x 20 units on a 100 page
    ell = ((0.1, 0.1), (0.5, 0.1), (0.5, 0.3), (0.3, 0.3), (0.3, 0.2), (0.1, 0.2))
    sheet = drawing(
        scale=Scale(status="estimated", m_per_unit=0.1, source="door widths"),
        rooms=(
            room(1, "living", 8.0, label="OH", polygon=rectangle),
            room(2, "balcony", 8.0, label="PARVEKE", polygon=rectangle),
            room(3, "bedroom", 6.0, label="MH", polygon=ell),
        ),
    )
    found = known_quantities(sheet)
    side = found[Query(measure="length", subject="room", name="OH").key()]
    assert (side.value, side.unit) == (4.0, "m")
    assert side.estimate == "measured on an estimated scale (door widths)"
    assert value(found, Query(measure="length", subject="room:balcony")) == 4.0
    assert (
        value(found, Query(measure="length", subject="room", name="MH")) is None
    )  # not a rectangle
    no_scale = drawing(rooms=(room(1, "living", 8.0, label="OH", polygon=rectangle),))
    assert (
        value(known_quantities(no_scale), Query(measure="length", subject="room", name="OH"))
        is None
    )


def test_the_apartment_is_the_sheet_s_one_dwelling() -> None:
    whole = Query(measure="area", subject="apartment")
    rooms = (
        room(1, "living", 10.0),
        room(2, "shaft", 1.0),
        room(3, "balcony", 5.0, outdoor=True),
    )
    assert value(known_quantities(drawing(rooms=rooms)), whole) == 10.0
    one = Apartment(id="a1", label="A", area_m2=55.0)
    assert value(known_quantities(drawing(rooms=rooms, apartments=(one,))), whole) == 55.0
    two = (one, Apartment(id="a2", label="B", area_m2=40.0))
    assert value(known_quantities(drawing(rooms=rooms, apartments=two)), whole) is None


def model_object(
    n: int, cls: str, storey: str, drawn: str | None = None, **q: float | str
) -> ModelObject:
    names = {key: q.pop(key) for key in ("name", "long_name") if key in q}
    return ModelObject.model_validate(
        {"id": f"m{n}", "class": cls, "storey": storey, "element": drawn, "quantities": q, **names}
    )


# A sheet of storey EG that draws one wall and one room of a model with more on EG and on OG.
MODEL = (
    model_object(1, "wall", "EG", "e1", length_m=3.0, side_area_m2=6.0, volume_m3=1.0),
    model_object(2, "wall", "EG", length_m=4.0, side_area_m2=8.0, volume_m3=2.0),
    model_object(3, "wall", "OG", length_m=5.0, side_area_m2=10.0, volume_m3=2.5),
    model_object(4, "slab", "EG", volume_m3=10.0),
    model_object(5, "door", "OG"),
    model_object(6, "space", "EG", "r1", area_m2=20.0, name="1.01", long_name="Office"),
    model_object(7, "space", "EG", area_m2=15.0, name="1.02", long_name="Store"),
)
SHEET = {
    "plans": (Plan(id="p1", page=1, box=BOX, storey="EG"),),
    "elements": (element(1, "wall", length_m=3.0, net_side_area_m2=6.0, net_volume_m3=1.0),),
    "rooms": (
        room(1, "other", 20.0, plan="p1", attrs={"ifc_name": "1.01", "ifc_long_name": "Office"}),
    ),
}


def test_a_storey_sum_counts_what_the_model_has_on_it_and_a_plan_count_what_the_sheet_draws() -> (
    None
):
    found = known_quantities(drawing(**SHEET, model_objects=MODEL))
    assert value(found, Query(measure="length", subject="wall", storey="EG")) == 7.0
    assert value(found, Query(measure="area", subject="wall", storey="EG")) == 14.0
    assert value(found, Query(measure="volume", subject="wall", storey="EG")) == 3.0
    assert value(found, Query(measure="volume", subject="slab", storey="EG")) == 10.0
    assert value(found, Query(measure="area", subject="room", storey="EG")) == 35.0
    store = Query(measure="area", subject="room", name="Store (1.02)", storey="EG")
    assert value(found, store) == 15.0
    assert value(found, Query(measure="area", subject="room", name="1.01", storey="EG")) == 20.0
    assert value(found, Query(subject="wall", storey="EG")) == 1  # shown on the plan
    assert value(found, Query(subject="room", storey="EG")) == 1
    walls = found[Query(subject="wall", model=True).key()]
    assert (walls.value, len(walls.marks)) == (3, 1)  # only the drawn wall has a mark
    assert value(found, Query(subject="room", model=True)) == 2
    assert value(found, Query(subject="door", model=True)) == 1
    assert value(found, Query(subject="wall", storey="OG", model=True)) == 1
    assert value(found, Query(subject="door")) == 0  # the sheet draws none
    assert found[store.key()].marks == ()


def test_without_a_model_the_storey_sums_are_the_drawn_elements() -> None:
    found = known_quantities(drawing(**SHEET))
    assert value(found, Query(measure="length", subject="wall", storey="EG")) == 3.0
    assert value(found, Query(measure="area", subject="room", storey="EG")) == 20.0
    assert Query(subject="wall", model=True).key() not in found


def test_a_storey_sum_the_model_cannot_give_is_unknown_even_if_the_drawn_elements_can() -> None:
    lacking = (MODEL[0], model_object(2, "wall", "EG"), MODEL[5], model_object(7, "space", "EG"))
    found = known_quantities(drawing(**SHEET, model_objects=lacking))
    assert Query(measure="length", subject="wall", storey="EG").key() not in found
    assert Query(measure="area", subject="room", storey="EG").key() not in found
    assert value(found, Query(measure="area", subject="room", name="1.01", storey="EG")) == 20.0


def test_a_space_the_model_states_no_area_for_has_the_area_of_the_room_the_sheet_draws() -> None:
    unstated = model_object(6, "space", "EG", "r1", name="1.01", long_name="Office")
    found = known_quantities(drawing(**SHEET, model_objects=(*MODEL[:5], unstated)))
    assert value(found, Query(measure="area", subject="room", name="Office", storey="EG")) == 20.0
    assert value(found, Query(measure="area", subject="room", storey="EG")) == 20.0
    undrawn = model_object(7, "space", "OG", name="2.01")
    found = known_quantities(drawing(**SHEET, model_objects=(*MODEL[:5], unstated, undrawn)))
    assert Query(measure="area", subject="room", name="2.01", storey="OG").key() not in found
    assert Query(measure="area", subject="room", storey="OG").key() not in found


def test_a_model_file_without_a_page_answers_from_its_objects_alone() -> None:
    found = known_quantities(
        Drawing(
            file="data/demo/m.ifc", pages=(), scale=Scale(status="no_scale"), model_objects=MODEL
        )
    )
    assert value(found, Query(subject="wall", storey="EG")) == 2
    assert value(found, Query(subject="room", storey="EG")) == 2
    assert value(found, Query(subject="door", storey="OG")) == 1
    assert value(found, Query(subject="door", storey="EG")) == 0
    assert value(found, Query(subject="wall", model=True)) == 3
    assert value(found, Query(measure="length", subject="wall", storey="EG")) == 7.0
    assert value(found, Query(measure="area", subject="room", name="Office", storey="EG")) == 20.0
    # asked plainly on the model file, a count is the model's ("How many walls are there?")
    assert value(found, Query(subject="wall")) == 3
    assert value(found, Query(subject="room")) == value(found, Query(subject="room", model=True))
    assert Query(subject="plan").key() not in found  # a model draws no plans


def test_a_model_file_gives_the_area_of_all_its_spaces_over_every_storey() -> None:
    """R4b-4: "net floor area of all indoor rooms" on a .ifc file is its spaces' areas summed."""
    file = Drawing(
        file="data/demo/m.ifc", pages=(), scale=Scale(status="scaled"), model_objects=MODEL
    )
    found = known_quantities(file)
    for indoor in (False, True):
        for model in (False, True):
            query = Query(measure="area", subject="room", indoor=indoor, model=model)
            assert value(found, query) == 35.0  # 20 + 15, both spaces of EG
    lacking = (*MODEL, model_object(8, "space", "OG", name="2.01"))  # a space with no area
    unknown = known_quantities(file.model_copy(update={"model_objects": lacking}))
    assert Query(measure="area", subject="room", indoor=True).key() not in unknown


def test_a_sheet_with_a_model_gives_no_whole_model_area() -> None:
    found = known_quantities(drawing(**SHEET, model_objects=MODEL))
    assert Query(measure="area", subject="room", indoor=True, model=True).key() not in found


def test_a_name_two_of_a_storey_s_spaces_share_names_neither() -> None:
    wcs = tuple(
        model_object(n, "space", "OG", area_m2=2.0, name=f"2.0{n}", long_name="WC") for n in (8, 9)
    )
    found = known_quantities(drawing(**SHEET, model_objects=(*MODEL, *wcs)))
    assert Query(measure="area", subject="room", name="WC", storey="OG").key() not in found
    assert value(found, Query(measure="area", subject="room", name="WC (2.08)", storey="OG")) == 2.0
    assert value(found, Query(measure="area", subject="room", storey="OG")) == 4.0


def door_entry(status: str, second: float) -> Conflict:
    return Conflict.model_validate(
        {
            "id": f"c-{status}",
            "quantity": "element_count",
            "subject": Subject(kind="class", ref="door"),
            "status": status,
            "tolerance": 0,
            "values": (
                MeasuredValue(value=2, method="parser"),
                MeasuredValue(value=second, method="ifc_model"),
            ),
            "resolution": Resolution(rule="the model", value=second)
            if status == "conflict"
            else None,
        }
    )


def test_a_second_reading_that_agrees_shows_on_the_quantity_without_changing_it() -> None:
    """api S2: first, second and agree. An agree entry goes on `agree`, a conflict on
    `conflict`; neither on a quantity nothing measured twice (single)."""
    doors = (element(1, "door"), element(2, "door"), element(3, "window"))
    agreed = known_quantities(drawing(elements=doors, conflicts=(door_entry("agree", 2),)))
    door = agreed[Query(subject="door").key()]
    assert (door.value, door.conflict) == (2, None)
    assert door.agree is not None and door.agree.status == "agree"
    assert [v.method for v in door.agree.values] == ["parser", "ifc_model"]
    window = agreed[Query(subject="window").key()]
    assert (window.agree, window.conflict) == (None, None)  # single
    disputed = known_quantities(drawing(elements=doors, conflicts=(door_entry("conflict", 3),)))
    door = disputed[Query(subject="door").key()]
    assert (door.value, door.agree) == (3, None)
    assert door.conflict is not None and door.conflict.status == "conflict"


def test_the_items_a_rule_leaves_out_are_listed_with_the_reason() -> None:
    """api B3: a sauna room is counted, so the stoves are left out; an indoor total and a
    dwelling's area leave out outdoor rooms (and shafts)."""
    stove_box = (0.5, 0.5, 0.6, 0.6)
    stove = Element.model_validate(
        {"id": "e9", "class": "sauna_stove", "page": 1, "box": stove_box, "attrs": {}}
    )
    sauna = known_quantities(drawing(elements=(stove,), rooms=(room(1, "sauna", None),)))
    found = sauna[Query(subject="sauna").key()]
    assert found.value == 1
    assert found.excluded == (
        (Mark(page=1, box=stove_box), "sauna rooms counted instead of sauna stoves"),
    )
    assert known_quantities(drawing(elements=(stove,)))[Query(subject="sauna").key()].excluded == ()
    rooms = (
        room(1, "living", 20.0),
        room(2, "balcony", 5.0, outdoor=True, box=stove_box),
        room(3, "shaft", 1.0, box=(0.3, 0.3, 0.4, 0.4)),
    )
    found = known_quantities(drawing(rooms=rooms))
    indoor = found[Query(measure="area", subject="room", indoor=True).key()]
    assert (indoor.value, indoor.excluded) == (
        21.0,
        ((Mark(page=1, box=stove_box), "outdoor room"),),
    )
    dwelling = found[Query(measure="area", subject="apartment").key()]
    assert dwelling.value == 20.0
    assert [why for _, why in dwelling.excluded] == ["outdoor room", "shaft"]


def test_a_sheet_s_count_leaves_out_what_another_storey_shows_through_the_cut() -> None:
    """R2-qa-1-1: the P2 sheet of an IFC draws 70 walls of P2 and 1 of P1 (a wall seen through
    the cut). Stage 8 counts the sheet's 70 against the model's 72 for P2 (here 2 against 4); the
    sheet's count is the same 70, so "How many walls are there?" carries that disagreement like
    the storey's row instead of answering 71 by one method. The P1 wall is listed as left out,
    with why."""
    below = (0.5, 0.5, 0.6, 0.6)
    walls = (
        element(1, "wall", storey="P2"),
        element(2, "wall", storey="P2"),
        Element.model_validate(
            {
                "id": "e3",
                "class": "wall",
                "page": 1,
                "box": below,
                "plan": "p1",
                "attrs": {"storey": "P1"},
            }
        ),
    )
    entry = Conflict.model_validate(
        {
            "id": "c1",
            "quantity": "element_count",
            "subject": Subject(kind="class", ref="wall"),
            "status": "conflict",
            "tolerance": 0,
            "values": (
                MeasuredValue(value=2, method="plan_drawing"),
                MeasuredValue(value=4, method="ifc_model"),
            ),
            "resolution": Resolution(rule="count what the sheet draws", value=2),
        }
    )
    found = known_quantities(
        drawing(
            plans=(Plan(id="p1", page=1, box=BOX, storey="P2"),),
            elements=walls,
            conflicts=(entry,),
        )
    )
    sheet = found[Query(subject="wall").key()]
    storey = found[Query(subject="wall", storey="P2").key()]
    assert (sheet.value, storey.value) == (2, 2)
    assert sheet.conflict is not None and sheet.conflict == storey.conflict
    assert sheet.excluded == (
        (Mark(page=1, box=below), "on storey P1 in the building model, seen through the cut"),
    )
    assert value(found, Query(subject="wall", storey="P1")) == 1


def test_no_rule_shows_the_user_an_internal_id_or_note() -> None:
    """R3 (F4): a card showed "room:sauna counted instead (sauna-room-else-stove)"; rule texts
    cited internal notes ("review-1 section 7", "(review-4)")."""
    texts = [found.text for found in vars(rules).values() if isinstance(found, CountingRule)]
    for text in texts:
        assert not re.search(r"review-\d|room:|_stove|\(\w+(-\w+)+\)", text), text


def _door_count_entry(drawn: int, modelled: int) -> dict[str, object]:
    return {
        "id": "c2",
        "quantity": "element_count",
        "subject": {"kind": "class", "ref": "door"},
        "status": "conflict",
        "tolerance": 0,
        "values": [
            {"value": drawn, "unit": "count", "method": "plan_drawing"},
            {"value": modelled, "unit": "count", "method": "ifc_model"},
        ],
        "resolution": None,
    }


def test_a_count_conflict_gives_each_value_the_positions_of_its_items() -> None:
    doors = (
        element(1, "door", mark="D1"),
        element(2, "door"),
        element(3, "door"),
        element(4, "window"),
    )
    sheet = drawing(
        plans=(Plan(id="p1", page=1, box=BOX, storey="0"),),
        elements=doors,
        model_objects=(
            ModelObject.model_validate({"id": "m1", "class": "door", "element": "e1"}),
            ModelObject.model_validate({"id": "m2", "class": "door"}),  # not drawn: no position
        ),
        conflicts=(_door_count_entry(3, 2),),
    )
    conflict = known_quantities(sheet)[Query(subject="door").key()].conflict
    assert conflict is not None
    drawn, modelled = conflict.value_marks
    assert [mark.label for mark in drawn] == ["D1", "door 2", "door 3"]  # no window
    assert all(mark.page == 1 and mark.box == BOX for mark in drawn)
    assert [mark.label for mark in modelled] == ["D1"]


def test_a_value_with_a_position_and_no_items_is_marked_where_it_was_read() -> None:
    sheet = drawing(
        rooms=(room(1, "other", 10.0, plan="p1"), room(2, "other", 20.0, plan="p1")),
        conflicts=(_room_count_entry(2, 3, picked=None),),
    )
    conflict = known_quantities(sheet)[Query(subject="room").key()].conflict
    assert conflict is not None
    drawn, modelled = conflict.value_marks
    assert [mark.label for mark in drawn] == ["r1", "r2"]  # the rooms the plan counted
    assert [(mark.label, mark.box) for mark in modelled] == [("ifc_model", OTHER)]


def test_a_room_area_conflict_marks_the_room_with_its_own_outline() -> None:
    outline = ((0.1, 0.1), (0.4, 0.1), (0.4, 0.3), (0.2, 0.3), (0.1, 0.2))
    entry = {
        "id": "c1",
        "quantity": "room_area",
        "subject": {"kind": "room", "ref": "r1"},
        "status": "conflict",
        "tolerance": 0.02,
        "values": [
            {"value": 12.5, "unit": "m2", "method": "printed_label", "page": 1, "box": BOX},
            {"value": 13.4, "unit": "m2", "method": "polygon_x_scale", "page": 1, "box": BOX},
        ],
        "resolution": None,
    }
    sheet = drawing(
        rooms=(room(1, "bedroom", 12.5, label="MH", polygon=outline),),
        conflicts=(entry,),
    )
    found = known_quantities(sheet)[Query(measure="area", subject="room", name="MH").key()]
    assert found.conflict is not None
    for marks in found.conflict.value_marks:
        assert [mark.polygon for mark in marks] == [outline]


def test_a_room_count_marks_each_room_with_its_outline_and_a_method_region_gets_none() -> None:
    outline = ((0.1, 0.1), (0.4, 0.1), (0.4, 0.3))
    sheet = drawing(
        rooms=(room(1, "other", 10.0, plan="p1", polygon=outline), room(2, "other", 20.0)),
        conflicts=(_room_count_entry(2, 3, picked=None),),
    )
    conflict = known_quantities(sheet)[Query(subject="room").key()].conflict
    assert conflict is not None
    drawn, modelled = conflict.value_marks
    assert [mark.polygon for mark in drawn] == [outline, None]
    assert [mark.polygon for mark in modelled] == [None]  # the model's region is no room outline


def test_a_conflict_with_no_item_or_position_has_no_marks() -> None:
    sheet = drawing(elements=(element(1, "door"),), conflicts=(_door_count_entry(0, 3),))
    conflict = known_quantities(sheet)[Query(subject="door").key()].conflict
    assert conflict is None  # the sheet's one door is not either value: not attached
    sheet = drawing(elements=(), conflicts=(_door_count_entry(0, 3),))
    found = known_quantities(sheet)
    assert all(q.conflict is None or q.conflict.value_marks == () for q in found.values())


ORDER_SCRIPT = """
from app.core.drawing.model import Drawing, ModelObject, Page, Room, Scale
from app.core.pipeline.takeoff import known_quantities

rooms = tuple(
    Room(id=f"r{at}", type="bedroom", label=f"Stanza {at}", page=1, area_m2=10.0 + at,
         box=(0.1 * at, 0.1, 0.1 * at + 0.05, 0.2),
         attrs={"number": f"1.0{at}", "name": f"Camera {at}"})
    for at in range(1, 6)
)
spaces = tuple(
    ModelObject(id=f"s{at}", class_="space", storey="EG", name=f"0.0{at}",
                long_name=f"Raum {at}", quantities={"area_m2": 5.0 + at})
    for at in range(1, 6)
)
drawing = Drawing(file="x.ifc", pages=(Page(page=1, width=9, height=9, unit="px"),),
                  scale=Scale(status="scaled"), rooms=rooms, model_objects=spaces)
print("\\n".join(known_quantities(drawing)))
"""


def test_the_takeoff_keys_come_in_the_same_order_whatever_the_hash_seed() -> None:
    """golden-311: three runs wrote ingest.json's 230 keys in three orders, because room_names
    and _space_names returned sets, whose order follows PYTHONHASHSEED."""
    import os
    import subprocess
    import sys

    orders = set()
    for seed in ("1", "2", "3", "4"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        done = subprocess.run([sys.executable, "-c", ORDER_SCRIPT], env=env, capture_output=True,
                              text=True, check=True)  # fmt: skip
        orders.add(done.stdout)
    assert len(orders) == 1
    keys = next(iter(orders)).splitlines()
    assert any("name=" in key for key in keys)  # the names are in it


def test_a_room_s_count_takes_its_fixtures_inside_and_the_doors_and_windows_in_its_walls() -> None:
    """Tudor's chat QA (floor9178): "How many doors does Bagno 1.01 have?" counted the sheet's
    13. Doors and windows sit in walls, outside every floor outline, so a door is the room's
    when it touches the outline (both rooms' between two rooms); a fixture when it is inside."""

    def at(n: int, cls: str, box: tuple[float, float, float, float]) -> Element:
        return Element.model_validate({"id": f"e{n}", "class": cls, "page": 1, "box": box})

    bath_outline = ((0.10, 0.10), (0.30, 0.10), (0.30, 0.30), (0.10, 0.30))
    hall_outline = ((0.32, 0.10), (0.60, 0.10), (0.60, 0.30), (0.32, 0.30))
    bath = room(1, "bathroom", 4.0, label="Bagno", polygon=bath_outline, attrs={"number": "1.01"})
    hall = room(2, "hall", 6.0, label="Corridoio", polygon=hall_outline, attrs={"number": "1.04"})
    boxed = room(3, "bedroom", 9.0, label="Stanza", attrs={"number": "1.02"})  # no outline
    items = (
        at(1, "door", (0.300, 0.18, 0.320, 0.22)),  # in the wall between bath and hall: both
        at(2, "door", (0.18, 0.090, 0.22, 0.100)),  # in the bath's top wall, up to its outline
        at(3, "toilet", (0.12, 0.12, 0.16, 0.16)),  # inside the bath
        at(4, "window", (0.60, 0.18, 0.62, 0.22)),  # in the hall's outer wall
        at(5, "door", (0.80, 0.80, 0.84, 0.84)),  # far from both
        at(6, "sink", (0.40, 0.40, 0.44, 0.44)),  # below the hall, outside it
    )
    found = known_quantities(drawing(rooms=(bath, hall, boxed), elements=items))
    count = {key: q.value for key, q in found.items() if "|name=" in key and "|" in key}

    def of(subject: str, name: str) -> int | float | None:
        return count.get(f"{subject}|name={name}")

    assert (of("door", "1.01"), of("toilet", "1.01"), of("window", "1.01")) == (2, 1, 0)
    assert of("door", "bagno") == 2  # by its printed label too
    assert (of("door", "1.04"), of("window", "1.04"), of("sink", "1.04")) == (1, 1, 0)
    assert of("door", "1.02") is None  # a box is not the room's shape
    assert found["door"].value == 3  # the sheet's count is unchanged


def test_a_wall_count_of_cut_solids_is_an_estimate_and_a_door_count_is_not() -> None:
    """B1: a sheet rendered from an IFC model draws walls, columns and other parts in one style,
    so its 'walls' are cut solids and the count may be too high (64 listed, 26 walls)."""
    note = "3 cut solids are listed as walls: the sheet draws walls, columns and other cut parts"
    elements = (element(1, "wall"), element(2, "wall"), element(3, "wall"), element(4, "door"))
    listed = known_quantities(drawing(elements=elements, notes=(note,)))
    walls = listed[Query(subject="wall").key()]
    assert walls.value == 3 and walls.estimate is not None
    assert walls.estimate == (  # plain words for a judge: no "cut solids" (review-455 S2)
        "3 solid shapes are counted as walls: this drawing shows walls, columns and other cut "
        "parts the same way, so there may be fewer walls"
    )
    assert listed[Query(subject="door").key()].estimate is None
    plain = known_quantities(drawing(elements=elements))  # walls a reader named walls
    assert plain[Query(subject="wall").key()].estimate is None


def test_a_door_count_read_from_drawn_shapes_is_an_estimate_a_window_count_is_not() -> None:
    """B1: an IFC-rendered sheet's doors are grouped from frame and swing shapes; a door drawn
    edge-on or over another is missed (17 read, 18 in the model), so the count may be low."""
    note = "2 doors are read from drawn shapes"
    elements = (element(1, "door"), element(2, "door"), element(3, "window"))
    listed = known_quantities(drawing(elements=elements, notes=(note,)))
    doors = listed[Query(subject="door").key()]
    assert doors.value == 2 and doors.estimate is not None
    # a missed door means more doors than read, never fewer (review-455 M1)
    assert doors.estimate == (
        "2 doors are read from drawn shapes: a door drawn edge-on or over another can be missed, "
        "so there may be more doors"
    )
    assert listed[Query(subject="window").key()].estimate is None


def test_one_solid_shape_is_worded_in_the_singular() -> None:
    """review-455 S4: three plain PDFs read one filled shape as a wall ("1 cut solids")."""
    note = "1 cut solids are listed as walls: the sheet draws walls, columns and other cut parts"
    listed = known_quantities(drawing(elements=(element(1, "wall"),), notes=(note,)))
    estimate = listed[Query(subject="wall").key()].estimate
    assert estimate is not None and estimate.startswith("1 solid shape is counted as a wall:")


def test_a_room_s_door_count_from_drawn_shapes_is_an_estimate_too() -> None:
    """review-455 S3: the per-room door counts use the same grouped doors as the sheet's."""
    outline = ((0.10, 0.10), (0.30, 0.10), (0.30, 0.30), (0.10, 0.30))
    office = room(1, "other", 4.0, label="Office", polygon=outline, attrs={"number": "1.02"})
    items = (
        Element.model_validate({"id": "e1", "class": "door", "page": 1,
                                "box": (0.300, 0.18, 0.320, 0.22)}),
        Element.model_validate({"id": "e2", "class": "window", "page": 1,
                                "box": (0.18, 0.090, 0.22, 0.100)}),
    )  # fmt: skip
    note = "1 doors are read from drawn shapes: a door drawn edge-on or over another can be missed"
    found = known_quantities(drawing(rooms=(office,), elements=items, notes=(note,)))
    door, window = found["door|name=1.02"], found["window|name=1.02"]
    assert door.value == 1 and door.estimate is not None and "more doors" in door.estimate
    assert window.value == 1 and window.estimate is None
    plain = known_quantities(drawing(rooms=(office,), elements=items))
    assert plain["door|name=1.02"].estimate is None
