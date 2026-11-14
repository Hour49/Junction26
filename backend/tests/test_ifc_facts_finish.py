from collections.abc import Sequence
from pathlib import Path

import ifcopenshell
import pytest

from app.adapters.ifc_model.facts_finish import finish_facts
from app.core.ifc_facts import Fact
from tests.ifc_models import IfcFile, Point, box


class _House(IfcFile):
    def door(
        self,
        storey: str,
        width: float,
        solid: tuple[Sequence[Point], float, float] | None = None,
    ) -> str:
        """A door of `storey`, its OverallWidth `width` m; without a solid it has no place."""
        door = self._rooted(
            "IfcDoor",
            Name="door",
            ObjectPlacement=None
            if solid is None
            else self._new("IfcLocalPlacement", RelativePlacement=self._origin),
            Representation=None if solid is None else self._body([solid]),
            OverallWidth=width * self._per_metre,
            OverallHeight=2.0 * self._per_metre,
        )
        self._rooted(
            "IfcRelContainedInSpatialStructure",
            RelatingStructure=self._file.by_guid(storey),
            RelatedElements=[door],
        )
        return door.GlobalId

    def skirting(self, storey: str, length: float) -> None:
        guid = self.element("IfcCovering", storey=storey, quantities={"Length": length})
        self._file.by_guid(guid).PredefinedType = "SKIRTINGBOARD"


def _house(millimetres: bool = False) -> bytes:
    """Rooms A (4 x 3 m) and B (3 x 3 m) with a 0.2 m wall and a 0.9 m door between them, a
    bathroom behind A through a 0.8 m door, a door of the storey above over A's wall, and a
    1.0 m door of B the model places nowhere but states as B's boundary."""
    model = _House(millimetres=millimetres)
    ground, upper = model.storey("Ground"), model.storey("Upper")
    model.space(ground, "A", "Living room", (box(0, 0, 4, 3), 0.0, 2.5))
    b = model.space(ground, "B", "Bedroom", (box(4.2, 0, 7.2, 3), 0.0, 2.5))
    model.space(ground, "C", "Bad", (box(0, 3.2, 2, 5.2), 0.0, 2.5))
    model.door(ground, 0.9, (box(4.0, 1.0, 4.2, 1.9), 0.0, 2.0))
    model.door(ground, 0.8, (box(0.5, 3.0, 1.3, 3.2), 0.0, 2.0))
    model.door(upper, 0.9, (box(1.0, -0.1, 1.9, 0.1), 3.0, 2.0))
    model.boundary(b, model.door(ground, 1.0))
    model.skirting(ground, 5.5 * (1000.0 if millimetres else 1.0))
    model.skirting(ground, 2.0 * (1000.0 if millimetres else 1.0))
    return model.ifc()


def _facts(data: bytes, tmp_path: Path) -> dict[tuple[str, str, str | None], Fact]:
    path = tmp_path / "house.ifc"
    path.write_bytes(data)
    found = finish_facts(ifcopenshell.open(str(path)))
    return {(fact.topic, fact.subject, fact.storey): fact for fact in found}


@pytest.mark.parametrize("millimetres", [False, True])
def test_a_room_takes_its_perimeter_less_the_doors_that_reach_its_floor(
    tmp_path: Path, millimetres: bool
) -> None:
    facts = _facts(_house(millimetres), tmp_path)
    length = {
        subject: fact.value
        for (topic, subject, _), fact in facts.items()
        if topic == "space.baseboard_length"
    }
    # A: 14 m less both its doors; the upper storey's door is over its wall, not on its floor.
    # B: 12 m less the shared door and the one the boundary names.
    assert length == {"A": 12.3, "B": 10.1, "all": 22.4}
    assert facts[("space.baseboard_length", "all", "Ground")].value == 22.4
    assert facts[("space.baseboard_length", "A", "Ground")].unit == "m"


def test_a_wet_room_is_left_out_with_its_reason(tmp_path: Path) -> None:
    facts = _facts(_house(), tmp_path)
    bathroom = facts[("space.baseboard_excluded", "C", "Ground")]
    assert bathroom.value == 7.2
    assert bathroom.source.startswith("excluded: wet room")
    assert ("space.baseboard_length", "C", "Ground") not in facts


def test_the_models_own_skirting_boards_are_summed(tmp_path: Path) -> None:
    facts = _facts(_house(millimetres=True), tmp_path)
    assert facts[("covering.skirting_length", "all", None)].value == 7.5
    assert facts[("covering.skirting_count", "all", "Ground")].value == 2


def test_a_gross_area_space_and_a_far_door_the_boundaries_name_are_left_out(
    tmp_path: Path,
) -> None:
    model = _House()
    ground = model.storey("Ground")
    room = model.space(ground, "A", "Office", (box(0, 0, 4, 3), 0.0, 2.5))
    model.space(ground, "B", "Office", (box(4.2, 0, 7.2, 3), 0.0, 2.5))
    model.space(ground, "G", "Gross area", (box(-0.2, -0.2, 7.4, 5.4), 0.0, 2.5))
    model.space(ground, "S", "Shaft", (box(5, 4, 6, 5), 0.0, 2.5))  # in G, not in a room
    model.boundary(room, model.door(ground, 0.9, (box(10, 10, 10.9, 10.2), 0.0, 2.0)))
    facts = _facts(model.ifc(), tmp_path)
    assert facts[("space.baseboard_length", "all", None)].value == 26.0
    assert facts[("space.baseboard_excluded", "G", "Ground")].source.startswith(
        "excluded: holds other spaces"
    )
