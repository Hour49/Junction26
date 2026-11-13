"""Stages 9-10 beyond plain counts: the counting rules as data, areas, lengths and volumes, and
the filters (label, name, apartment, storey) a query looks a quantity up by."""

from app.core.answering.model import Query
from app.core.drawing.model import Apartment, Drawing, Element, Page, Plan, Room, Scale
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


def test_an_element_quantity_one_element_lacks_is_unknown_and_the_model_is_never_a_sheet() -> None:
    found = known_quantities(
        drawing(elements=(element(1, "wall", length_m=3.0), element(2, "wall")))
    )
    assert Query(measure="length", subject="wall").key() not in found
    assert value(found, Query(subject="wall")) == 2
    assert Query(subject="wall", model=True).key() not in found
