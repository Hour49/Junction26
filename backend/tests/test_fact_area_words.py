"""A model's two space areas, said so they cannot be read as one another (Tudor's QA batch 1,
#430 B5): the takeoff's room areas are each space's footprint in the model's geometry (rule
model-spaces), while a file's Qto NetFloorArea can be smaller (1939.37 against a 2266.66
footprint on an office model). The fact answer names which is which."""

from app.core.answering.facts import fact_text
from app.core.ifc_facts import Fact, FactSheet
from app.core.ifc_question import parse_ifc_question


def fact(topic: str, subject: str, value: float | str, storey: str | None = None) -> Fact:
    unit = None if isinstance(value, str) else "m2"
    return Fact(
        topic=topic,
        subject=subject,
        value=value,
        unit=unit,
        storey=storey,
        discipline="architecture",
        source="test",
    )


OFFICE = FactSheet(
    model="office",
    disciplines=["architecture"],
    facts=[
        fact("space.long_name", "001", "Office", storey="EG"),
        fact("space.long_name", "002", "Hall", storey="EG"),
        fact("space.net_floor_area", "001", 1000.0, storey="EG"),
        fact("space.net_floor_area", "002", 939.37, storey="EG"),
        fact("space.net_floor_area", "all", 1939.37),
        fact("space.area", "001", 1200.0, storey="EG"),
        fact("space.area", "002", 1066.66, storey="EG"),
        fact("space.area", "all", 2266.66),
    ],
)


def test_the_net_area_and_the_footprint_each_say_where_they_come_from() -> None:
    query = parse_ifc_question("What is the net floor area of all indoor rooms?")
    assert query is not None
    lines = (fact_text(query, OFFICE) or "").splitlines()
    assert lines[:3] == [
        "Spaces: total 1939.37 m²",  # the net floor area the file states answers "net"
        "Sum of the spaces' net floor area as the file states it: 1939.37 m²",
        "Sum of the spaces' footprint area from the model's geometry: 2266.66 m²",
    ]
