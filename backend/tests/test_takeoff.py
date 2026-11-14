"""Stages 9-10 beyond plain counts: the counting rules as data, areas, lengths and volumes, and
the filters (label, name, apartment, storey) a query looks a quantity up by."""

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
    assert value(found, Query(subject="door")) == 2
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
    assert area.estimate == "an estimated scale (door widths), uncertainty 0.15"
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
        == "1 of 2 room areas estimated (geometry_x_estimate, uncertainty up to 0.35)"
    )
    assert found[Query(measure="area", subject="room", name="K").key()].estimate is None
    # a printed (exact) area does not rest on the sheet's estimated scale; an unset one does
    guessed = Scale(status="estimated", m_per_unit=0.02, source="door widths")
    on_guess = known_quantities(drawing(scale=guessed, rooms=rooms))
    assert on_guess[Query(measure="area", subject="room", name="K").key()].estimate is None
    # an outline at an estimated scale also says how that scale was estimated
    assert on_guess[Query(measure="area", subject="room").key()].estimate == (
        "1 of 2 room areas estimated (geometry_x_estimate, uncertainty up to 0.35), "
        "at an estimated scale (door widths)"
    )
    unset = known_quantities(drawing(scale=guessed, rooms=(room(3, "hall", 5.0, label="ET"),)))
    assert unset[Query(measure="area", subject="room").key()].estimate == (
        "an estimated scale (door widths)"
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
    assert side.estimate == "an estimated scale (door widths)"
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
        (Mark(page=1, box=stove_box), f"room:sauna counted instead ({SAUNA_ROOM_ELSE_STOVE.id})"),
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
