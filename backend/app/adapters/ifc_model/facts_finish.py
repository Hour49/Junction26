"""The finish facts of an IFC model (app/core/ifc_facts.py): how many metres of baseboard
(skirting) its rooms take, read from the spaces' footprints and the doors in their walls.

- `space.baseboard_length` (m), per space, subject its name as facts_arch.py names it: the
  perimeter of the space's footprint (objects.py's `_solid`, the same footprint as `space.area`;
  holes such as a free-standing column count, they get skirting too) less the width of every door
  in its walls that reaches its floor. The skirting runs up to the door frame, so a door takes
  away its OverallWidth (else its Qto Width). Summed per storey and for the model, subject "all".
- A door is in a space's wall when the middle of its shape seen from above, else its placement
  point, is within WALL_SLACK_M of the footprint's outline and its bottom within FLOOR_SLACK_M
  of the space's floor (a door of the storey above stands over the same outline). A door
  between two rooms counts in both. Only a door with neither shape nor placement is taken from
  the model's IfcRelSpaceBoundary: on the dev models those link doors 0.5 to 12 m from the
  space's outline, where the geometry finds the ones the boundaries leave out.
- Spaces with no baseboard are not summed: they get `space.baseboard_excluded` with the length
  they would have had and the reason in `source`. They are tiled wet rooms and saunas, shafts,
  balconies, roofs and outdoor spaces, by the room type of their name (ifc_render.py's
  multilingual ROOM_WORDS), and a space that holds two or more spaces on its floor: a
  gross-area or zone space drawn around the rooms, whose skirting the rooms already have.
- `covering.skirting_length` (m) and `covering.skirting_count`: the model's own skirting boards,
  IfcCovering SKIRTINGBOARD, by their Qto Length, per storey and for the model, to compare with.
"""

import re
from collections import defaultdict
from collections.abc import Hashable, Iterator, Mapping
from typing import Any

import ifcopenshell.geom
from shapely import STRtree
from shapely.geometry.base import BaseGeometry

from app.adapters.ifc_model.facts_arch import _fact, _quantities
from app.adapters.ifc_model.objects import _solid, _storey, _unit_scales
from app.adapters.ifc_model.windows import Points, Solid, _placed, _shape
from app.adapters.vector_pdf.ifc_render import room_type
from app.core.drawing.model import RoomType
from app.core.ifc_facts import Fact

WALL_SLACK_M = 0.35  # door middle to the room's outline: half a wall up to 0.7 m thick
FLOOR_SLACK_M = 0.3  # a door's bottom to the room's floor (thresholds, wet-room steps)
HELD = 0.5  # share of a smaller space's floor a gross-area space covers
SAME_FLOOR_M = 1.0  # an atrium's galleries are a storey up, a gross area's rooms within this
NO_BASEBOARD: Mapping[RoomType, str] = {
    "bathroom": "wet room, tiled",
    "wc": "wet room, tiled",
    "sauna": "sauna, tiled or panelled",
    "shaft": "shaft",
    "balcony": "balcony",
    "outdoor": "outdoor",
}

ROOF = re.compile(r"\broof\b", re.IGNORECASE)  # a roof terrace: ROOM_WORDS has no word for it

# guid, width in m, the middle seen from above and the bottom's height (None: not placed)
type _Door = tuple[str, float | None, tuple[BaseGeometry, float] | None]


def finish_facts(file: Any) -> list[Fact]:
    """`file`: an open ifcopenshell file (lazy mode is fine)."""
    scales = _unit_scales(file)
    return [*_baseboards(file, scales["LENGTHUNIT"]), *_skirtings(file, scales["LENGTHUNIT"])]


def _baseboards(file: Any, m_per_unit: float) -> Iterator[Fact]:
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    doors = _doors(file, m_per_unit)
    stated: dict[str, set[str]] = defaultdict(set)
    for rel in file.by_type("IfcRelSpaceBoundary"):
        space, door = rel.RelatingSpace, rel.RelatedBuildingElement
        if space is not None and door is not None and door.is_a("IfcDoor"):
            stated[space.GlobalId].add(door.GlobalId)
    spaces = [
        (space, solid)
        for space in file.by_type("IfcSpace")
        if (solid := _solid(space, settings)) is not None and solid.footprint.area
    ]
    tree = STRtree([solid.footprint for _, solid in spaces])
    sums: dict[tuple[str, str | None], float] = defaultdict(float)
    for space, solid in spaces:
        found = _storey(space)
        storey = None if found is None else found.Name
        name = space.Name or space.LongName or space.GlobalId
        perimeter = solid.footprint.length
        linked = [door for door in doors if _in_wall(door, solid, stated[space.GlobalId])]
        widths = [width for _, width, _ in linked if width]
        length = max(perimeter - sum(widths), 0.0)
        how = f"footprint perimeter {perimeter:.2f} m - {len(widths)} doors {sum(widths):.2f} m"
        if len(widths) < len(linked):
            how += f" ({len(linked) - len(widths)} doors without a width)"
        label = " ".join(part for part in (space.LongName, space.Name) if part)
        kind = "outdoor" if ROOF.search(label) else room_type(label)
        reason = NO_BASEBOARD.get(kind)
        if reason is None and _holds(solid, [spaces[i][1] for i in tree.query(solid.footprint)]):
            reason, kind = "holds other spaces: a gross-area or zone space", "other"
        topic = "space.baseboard_length" if reason is None else "space.baseboard_excluded"
        source = how if reason is None else f"excluded: {reason} ({kind}); {how}"
        yield _fact(topic, name, length, "m", source, storey)
        for where in {None, storey}:
            sums[(topic, where)] += length
    for (topic, storey), total in sums.items():
        yield _fact(topic, "all", total, "m", "sum over spaces", storey)


def _doors(file: Any, m_per_unit: float) -> list[_Door]:
    """Every door: its GlobalId, its width in m, where it is seen from above (the middle of its
    shape, else its placement point) and the height of its bottom."""
    settings = ifcopenshell.geom.settings()  # shapes in each door's own coordinates
    built: dict[Hashable, Points | None] = {}
    doors: list[_Door] = []
    for door in file.by_type("IfcDoor"):
        width = door.OverallWidth or _quantities(door).get("Width")
        seen = _shape(door, settings, built, m_per_unit) or _placed(door, m_per_unit)
        at = None if seen is None else (seen[0].centroid, seen[1])
        doors.append((door.GlobalId, None if width is None else width * m_per_unit, at))
    return doors


def _in_wall(door: _Door, solid: Solid, stated: set[str]) -> bool:
    guid, _, at = door
    if at is None:
        return guid in stated
    middle, low = at
    return (
        abs(low - solid.low) <= FLOOR_SLACK_M
        and solid.footprint.boundary.distance(middle) <= WALL_SLACK_M
    )


def _holds(solid: Solid, near: list[Solid]) -> bool:
    """Whether the space covers most of two or more smaller spaces on its floor. One is not
    enough: a shaft drawn inside a plant room, a urinal inside a washroom."""
    held = sum(
        other.footprint.area < solid.footprint.area
        and abs(other.low - solid.low) <= SAME_FLOOR_M
        and solid.footprint.intersection(other.footprint).area > HELD * other.footprint.area
        for other in near
    )
    return held >= 2


def _skirtings(file: Any, m_per_unit: float) -> Iterator[Fact]:
    sums: dict[tuple[str, str | None], float] = defaultdict(float)
    for covering in file.by_type("IfcCovering"):
        if covering.PredefinedType != "SKIRTINGBOARD":
            continue
        found = _storey(covering)
        storey = None if found is None else found.Name
        length = _quantities(covering).get("Length")
        for where in {None, storey}:
            sums[("covering.skirting_count", where)] += 1
            if length is not None:
                sums[("covering.skirting_length", where)] += length * m_per_unit
    for (topic, storey), total in sums.items():
        if topic.endswith("count"):
            yield _fact(topic, "all", int(total), "count", "IfcCovering SKIRTINGBOARD", storey)
        else:
            yield _fact(topic, "all", total, "m", "Qto Length of IfcCovering SKIRTINGBOARD", storey)
