"""The objects of an IFC building model, through ifcopenshell (LGPL, an unmodified dependency:
docs/decisions/0006-lgpl-dependencies.md). Ported from prototypes/extraction-gold/ifc_gold.py.

What is read, and the definitions the dataset's answers follow (reviews 5 and 6):

- Elements: every IfcDoor, IfcWindow, IfcWall, IfcColumn, IfcBeam, IfcSlab, IfcRailing and
  IfcStair, subtypes included (IfcWallStandardCase is a wall). An IfcStair that is a part of
  another IfcStair is not a stair of its own.
- Rooms: every IfcSpace, with its Name (the room number), LongName and its floor area: the
  footprint of its solid, which is what the dataset's room areas equal (266 of 266 dev answers
  asked on a model file; on a sheet it is the room's drawn outline, sheet.py). The area a file
  states for a space is not read: most files state none, and where one does it follows other
  rules (an attic room counts only where one can stand).
- Storey: the IfcBuildingStorey an object is contained in, or that the object it is a part of
  is contained in. The storey's name is how questions and sheets refer to it.
- Parts: the objects an object is decomposed into (the layers of a wall, the flights of a
  stair). A sheet may draw the parts and not the object.
- A space's windows: the model's windows that belong to it, drawn on a sheet or not
  (windows.py), for a check that asks whether a room has one.
- A wall's and a slab's quantities are the file's own (its Qto sets), in metres: a wall's
  Length, NetSideArea and NetVolume, a slab's NetVolume. They are the exporter's numbers, not
  measured from geometry, and they are what the dataset's sums add up. An object without a
  quantity has none here, and neither has a space without a solid.

Only plain data leaves this module, so the parsed file can be dropped after reading. The file
is read from disk in ifcopenshell's lazy mode, which parses an object when it is looked at: on
the dataset's largest model (343 MB) that is 0.8 GB of memory and 3 s, where parsing the whole
text took 3.2 GB and 8 s. ifcopenshell 0.9.0.post1 does not give a parsed file's memory back when
it is dropped, so what one model takes stays taken, and many models read in one run add up.
"""

import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import ifcopenshell.util.unit
from shapely.geometry import Polygon
from shapely.ops import unary_union

from app.adapters.ifc_model.windows import Solid, windows_of_spaces
from app.core.drawing.model import ElementClass, QuantityKey
from app.core.errors import InvalidInputError

CLASSES: Mapping[str, ElementClass] = {
    "IfcDoor": "door",
    "IfcWindow": "window",
    "IfcWall": "wall",
    "IfcColumn": "column",
    "IfcBeam": "beam",
    "IfcSlab": "slab",
    "IfcRailing": "railing",
    "IfcStair": "stair",
}
# Per class: the file's quantity name -> the key it has in the drawing model's `model_objects`
# and the unit it is stated in.
QUANTITIES: Mapping[ElementClass, Mapping[str, tuple[QuantityKey, str]]] = {
    "wall": {
        "Length": ("length_m", "LENGTHUNIT"),
        "NetSideArea": ("side_area_m2", "AREAUNIT"),
        "NetVolume": ("volume_m3", "VOLUMEUNIT"),
    },
    "slab": {"NetVolume": ("volume_m3", "VOLUMEUNIT")},
}
MAX_CLIMB = 10  # steps from an object up to its storey
FLAT = 1e-12  # m2: a triangle that stands upright covers no floor


@dataclass(frozen=True)
class IfcObject:
    guid: str  # the GlobalId, which a rendered sheet tags the object's shape with
    source_class: str  # as the file names it, e.g. IfcWallStandardCase
    storey: str | None
    parts: tuple[str, ...]  # GlobalIds of everything it is decomposed into, at any depth
    name: str | None
    long_name: str | None
    quantities: Mapping[QuantityKey, float]  # in metres, m2 or m3
    # A space: the GlobalIds of the model's windows that belong to it; None: not known
    windows: tuple[str, ...] | None = None


@dataclass(frozen=True)
class Model:
    storeys: tuple[str, ...]  # names, in the file's order
    elements: Mapping[ElementClass, tuple[IfcObject, ...]]
    spaces: tuple[IfcObject, ...]  # quantities: {"area_m2": ...} when the space has a solid

    def on_storey(self, class_: ElementClass, storey: str | None) -> tuple[IfcObject, ...]:
        return tuple(found for found in self.elements[class_] if found.storey == storey)


def read_model(data: bytes) -> Model:
    with tempfile.NamedTemporaryFile(suffix=".ifc") as on_disk:
        # Bytes that are not UTF-8 would fail later, when the text they are in is looked at.
        on_disk.write(data.decode("utf-8", errors="replace").encode())
        on_disk.flush()
        opened: Any = ifcopenshell.open  # its typed overloads (0.9.0.post1) leave `lazy` out
        try:
            file = opened(on_disk.name, lazy=True)
            projects = file.by_type("IfcProject")  # a text that is no IFC opens, to no schema
        except Exception as error:  # ifcopenshell raises its own and plain RuntimeErrors
            raise InvalidInputError(f"not an IFC file ifcopenshell can read: {error}") from error
        if not projects:
            raise InvalidInputError("not an IFC model: it has no IfcProject, so no units")
        return _model(file)  # while the file is on disk: lazy reading goes back to it


def _model(file: Any) -> Model:
    scales = _unit_scales(file)
    elements: dict[ElementClass, tuple[IfcObject, ...]] = {}
    for ifc_class, class_ in CLASSES.items():
        wanted = QUANTITIES.get(class_, {})
        found: list[IfcObject] = []
        for entity in file.by_type(ifc_class):
            if class_ == "stair" and _part_of_a_stair(entity):
                continue
            stated = _stated(entity) if wanted else {}
            quantities: dict[QuantityKey, float] = {
                key: round(stated[name] * scales[unit], 4)
                for name, (key, unit) in wanted.items()
                if name in stated
            }
            found.append(_object(entity, quantities))
        elements[class_] = tuple(found)
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    solids = {
        entity.GlobalId: solid
        for entity in file.by_type("IfcSpace")
        if (solid := _solid(entity, settings)) is not None
    }
    windows = windows_of_spaces(file, solids, settings, scales["LENGTHUNIT"])
    spaces: list[IfcObject] = []
    for entity in file.by_type("IfcSpace"):
        solid = solids.get(entity.GlobalId)
        area = None if solid is None else solid.footprint.area or None
        spaces.append(
            _object(
                entity,
                {} if area is None else {"area_m2": round(area, 4)},
                windows.get(entity.GlobalId),
            )
        )
    storeys = tuple(storey.Name for storey in file.by_type("IfcBuildingStorey") if storey.Name)
    return Model(storeys=storeys, elements=elements, spaces=tuple(spaces))


def _unit_scales(file: Any) -> dict[str, float]:
    """What a length, area or volume of the file is multiplied by to get metres, m2 or m3. A file
    that names no area or volume unit states them in its length unit squared and cubed."""
    length = ifcopenshell.util.unit.calculate_unit_scale(file)
    scales = {"LENGTHUNIT": length}
    for unit, power in (("AREAUNIT", 2), ("VOLUMEUNIT", 3)):
        named = ifcopenshell.util.unit.get_project_unit(file, unit) is not None
        scales[unit] = (
            ifcopenshell.util.unit.calculate_unit_scale(file, unit) if named else length**power
        )
    return scales


def _stated(entity: Any) -> dict[str, float]:
    """Every numeric quantity the file states for an object, by name, from all its Qto sets."""
    sets = ifcopenshell.util.element.get_psets(entity, qtos_only=True)
    return {
        name: float(value)
        for quantities in sets.values()
        for name, value in quantities.items()
        if isinstance(value, int | float) and not isinstance(value, bool) and name != "id"
    }


def _solid(space: Any, settings: Any) -> Solid | None:
    """A space's solid: the floor it covers (its triangles laid flat, each spot counted once: a
    space under a stair has its floor in steps) and its lowest and highest point. ifcopenshell
    gives the solid in metres whatever the file's unit. None: the space has no solid."""
    try:
        shape: Any = ifcopenshell.geom.create_shape(settings, space)
    except RuntimeError:  # no representation, or one the geometry kernel cannot build
        return None
    solid = shape.geometry
    corners = list(zip(solid.verts[0::3], solid.verts[1::3], strict=True))
    triangles = (
        Polygon([corners[a], corners[b], corners[c]])
        for a, b, c in zip(solid.faces[0::3], solid.faces[1::3], solid.faces[2::3], strict=True)
    )
    footprint = unary_union([triangle for triangle in triangles if triangle.area > FLAT])
    return Solid(footprint, min(solid.verts[2::3]), max(solid.verts[2::3]))


def _object(
    entity: Any,
    quantities: Mapping[QuantityKey, float],
    windows: tuple[str, ...] | None = None,
) -> IfcObject:
    storey = _storey(entity)
    return IfcObject(
        guid=entity.GlobalId,
        source_class=entity.is_a(),
        storey=None if storey is None else storey.Name,
        parts=tuple(_parts(entity)),
        name=entity.Name,
        long_name=getattr(entity, "LongName", None),
        quantities=quantities,
        windows=windows,
    )


def _storey(entity: Any) -> Any | None:
    """The storey that contains `entity`, or that contains what it is a part of."""
    current = entity
    for _ in range(MAX_CLIMB):
        if current is None:
            return None
        if current.is_a("IfcBuildingStorey"):
            return current
        contained = getattr(current, "ContainedInStructure", None) or ()
        whole = getattr(current, "Decomposes", None) or ()
        if contained:
            current = contained[0].RelatingStructure
        elif whole:
            current = whole[0].RelatingObject
        else:
            return None
    return None


def _children(entity: Any) -> list[Any]:
    return [
        child
        for relation in getattr(entity, "IsDecomposedBy", None) or ()
        for child in relation.RelatedObjects
    ]


def _parts(entity: Any) -> list[str]:
    parts: list[str] = []
    stack = _children(entity)
    while stack:
        part = stack.pop()
        parts.append(part.GlobalId)
        stack += _children(part)
    return parts


def _part_of_a_stair(entity: Any) -> bool:
    whole = getattr(entity, "Decomposes", None) or ()
    return bool(whole) and whole[0].RelatingObject.is_a("IfcStair")
