"""The architecture and structural facts of an IFC model (app/core/ifc_facts.py): the project,
its storeys, its spaces, and its building elements by type.

What is read, and the conventions the facts follow:

- Every number is in metres, m2 or m3 (unit "m", "m2", "m3"), whatever the file's units; a count
  has unit "count", a name or a flag is text with no unit.
- `storey` None: the whole building. A fact with a storey counts that storey only.
- Element facts: `<entity>.<measure>` with subject "all", "external", "internal",
  "load_bearing", "non_load_bearing" or "predefined:<TYPE>" sums or counts that part of the
  class (e.g. "wall.length" / "external"); `<entity>_type.<measure>` is per type, subject the
  type's name. Some classes (ONE_BY_ONE) also get one fact per element, subject its name
  (`<entity>.global_id` among them, for a question that names an element by its GUID).
- A type's name is its IfcTypeObject's Name, else the element's ObjectType, else the element's
  Name without the trailing Revit id (":123456").
- Quantities are the file's own (its Qto sets, e.g. Length, NetSideArea, NetVolume), summed
  where they add up. A door's and a window's width and height are its OverallWidth and
  OverallHeight. A thickness is the sum of the material layers, else the Qto width (depth for a
  slab or a roof).
- A space's subject is its Name (often its number); its LongName is a fact of its own and the
  key of the `space_function.*` sums. `space.area` is the footprint of its solid, read by
  objects.py's own `_solid`, so a room has one area wherever it is asked. What the file states
  is kept apart: the Qto areas (`space.net_floor_area`, `space.gross_floor_area`) and the area
  the authoring tool writes in a property set (`space.stated_area`, STATED_AREAS). A space's
  `space.height` is its Qto Height, else the depth of its upright body extrusion.
- Derived numbers are computed here, never by the answering side (suffixed topics, whole
  building unless a storey is set): `<entity>.<measure>.min|max|average` per part,
  `<entity>.<measure>.per_storey` (the total over the storeys that hold the class),
  `<entity>.count|volume.by_material` and `.by_material_kind` (MATERIAL_KINDS, e.g.
  "concrete"; `element.*` over every class), `structural.count.total` (STRUCTURAL classes and
  the bearing walls) and `foundation.<measure>.total` (FOUNDATION; subject "all" or the class).
"""

import re
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import ifcopenshell.geom
import ifcopenshell.util.element as element_util

from app.adapters.ifc_model.objects import _solid, _storey, _unit_scales
from app.core.ifc_facts import Discipline, Fact

CLASSES: Mapping[str, tuple[str, Discipline]] = {
    "IfcWall": ("wall", "architecture"),
    "IfcCurtainWall": ("curtain_wall", "architecture"),
    "IfcDoor": ("door", "architecture"),
    "IfcWindow": ("window", "architecture"),
    "IfcRoof": ("roof", "architecture"),
    "IfcStair": ("stair", "architecture"),
    "IfcStairFlight": ("stair_flight", "architecture"),
    "IfcRamp": ("ramp", "architecture"),
    "IfcRailing": ("railing", "architecture"),
    "IfcCovering": ("covering", "architecture"),
    "IfcFurnishingElement": ("furniture", "architecture"),
    "IfcTransportElement": ("transport", "architecture"),
    "IfcSlab": ("slab", "structural"),
    "IfcColumn": ("column", "structural"),
    "IfcBeam": ("beam", "structural"),
    "IfcMember": ("member", "structural"),
    "IfcPlate": ("plate", "structural"),
    "IfcFooting": ("footing", "structural"),
    "IfcPile": ("pile", "structural"),
    "IfcReinforcingBar": ("reinforcing_bar", "structural"),
}
ONE_BY_ONE = frozenset(
    {"door", "window", "slab", "roof", "column", "beam", "stair", "railing", "curtain_wall"}
)
# Qto names read, and whether a class's elements add them up (False: a dimension, listed).
QUANTITIES: Mapping[str, bool] = {
    "Length": True,
    "NetArea": True,
    "GrossArea": True,
    "NetSideArea": True,
    "GrossSideArea": True,
    "NetFootprintArea": True,
    "GrossFootprintArea": True,
    "OuterSurfaceArea": True,
    "NetVolume": True,
    "GrossVolume": True,
    "Area": True,  # Area and Volume: as Revit states them (DIMENSIONS), no Qto names
    "Volume": True,
    "Width": False,
    "Height": False,
    "Depth": False,
    "Perimeter": False,
    "CrossSectionArea": False,
    # Of the profile the body is extruded from (EXTRUDED): a column's or a beam's section.
    "ProfileWidth": False,
    "ProfileDepth": False,
    "ProfileDiameter": False,
}
DIMENSION_SETS = frozenset({"PSet_Revit_Dimensions"})
DIMENSIONS = ("Length", "Area", "Volume")
SPACE_QUANTITIES = (
    "NetFloorArea",
    "GrossFloorArea",
    "NetPerimeter",
    "GrossPerimeter",
    "Height",
    "NetVolume",
    "GrossVolume",
)
SPACE_SUMS = ("NetFloorArea", "GrossFloorArea", "NetVolume", "GrossVolume")
# The area an authoring tool states in its own property set: ArchiCAD, Revit, older ArchiCAD.
STATED_AREAS = ("Calculated Area", "Area", "ROOM AREA")
LAYERED = frozenset({"wall", "curtain_wall", "covering", "plate"})  # thickness: the Qto Width
SLABBED = frozenset({"slab", "roof"})  # thickness: the Qto Depth, else Width
REVIT_ID = re.compile(r":\d+$")
EXTRUDED = frozenset({"column", "beam", "member", "pile"})
STRUCTURAL = ("slab", "column", "beam", "member", "plate", "footing", "pile")
# A foundation: a footing, a pile, a base slab, or an element whose type name says so.
FOUNDATION_CLASSES = ("slab", "wall", "beam", "column", "footing", "pile")
FOUNDATION = re.compile(r"found|fundam|fundat|funder|footing|\bpad\b|poer|paal|\bpile", re.I)
# Words of a material's name, by kind; the first kind that matches (masonry before concrete:
# "Concrete Masonry Units").
MATERIAL_KINDS: Mapping[str, re.Pattern[str]] = {
    kind: re.compile(words, re.I)
    for kind, words in (
        ("masonry", r"masonry|brick|\bcmu\b|tegl|ziegel|mauerwerk|kalkzand|kalksand"),
        ("concrete", r"concrete|beton|\bstb\b|\bc\d\d/\d\d|cast.in"),
        ("steel", r"steel|staal|stahl|stål|\bs[23]\d5\b"),
        ("timber", r"wood|timber|lumber|plywood|glulam|hout|holz|\btræ|\btre\b"),
        ("insulation", r"insul|isolat|dämm"),
        ("gypsum", r"gypsum|plaster|gips"),
        ("glass", r"glass|glas"),
    )
}
GROSS_VOLUME_SANE = 10  # a GrossVolume above 10 x the NetVolume is a unit slip of the file
MAX_NESTING = 5  # mapped items and boolean results opened to find an extrusion


@dataclass(frozen=True)
class _Element:
    name: str
    type_name: str
    group_name: str  # its Name without a Revit id: ArchiCAD files group their elements by it
    family_name: str  # Revit's "Family:Type" (its ObjectType without the id), else type_name
    storey: str | None
    predefined: str | None
    measures: Mapping[str, float]  # by Qto name (and NominalDiameter, BarLength), in m/m2/m3
    layers: tuple[tuple[str, float], ...]  # material and thickness in m, outside in
    materials: tuple[str, ...]
    thickness: float | None
    flags: Mapping[str, bool]  # IsExternal, LoadBearing, as the file states them
    fire_rating: str | None
    global_id: str


def arch_facts(file: Any) -> list[Fact]:
    """`file`: an open ifcopenshell file (lazy mode is fine)."""
    scales = _unit_scales(file)
    facts = [*_project(file, scales), *_storeys(file, scales), *_spaces(file, scales)]
    volumes: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    by_key: dict[str, list[_Element]] = {}
    for ifc_class, (key, discipline) in CLASSES.items():
        elements = [_element(entity, key, scales) for entity in file.by_type(ifc_class)]
        by_key[key] = elements
        facts += _sums(key, discipline, elements)
        facts += _stats(key, discipline, elements)
        facts += _by_material(key, discipline, elements)
        facts += _distributions(key, discipline, elements)
        facts += _types(f"{key}_type", discipline, _grouped(elements, "type_name"))
        # The same types under Revit's "Family:Type" name too, where the file writes one.
        aliased = [e for e in elements if e.family_name != e.type_name]
        facts += _sums(f"{key}_type", discipline, aliased, "family_name")
        facts += _types(f"{key}_type", discipline, _grouped(aliased, "family_name"))
        names = _grouped(elements, "group_name")
        if len(names) < len(elements) and names != _grouped(elements, "type_name"):
            facts += _sums(f"{key}_name", discipline, elements, "group_name", by_storey=False)
            facts += _types(f"{key}_name", discipline, names)
        if key in ONE_BY_ONE:
            facts += _one_by_one(key, discipline, elements)
        for element in elements:
            for material, volume in _material_volumes(element):
                volumes[material] += volume
            for material in set(element.materials):
                counts[material] += 1
    for material, count in counts.items():
        facts.append(_fact("material.element_count", material, count, "count", "material"))
    for material, volume in volumes.items():
        facts.append(
            _fact("material.net_volume", material, volume, "m3", "NetVolume by layer thickness")
        )
    everything = [e for elements in by_key.values() for e in elements]
    facts += _by_material("element", "architecture", everything, ("by_material_kind",))
    return [*facts, *_structural(by_key), *_foundation(by_key)]


def _fact(
    topic: str,
    subject: str,
    value: float | int | str,
    unit: str | None,
    source: str,
    storey: str | None = None,
    discipline: Discipline = "architecture",
) -> Fact:
    if isinstance(value, float):
        value = round(value, 6 if unit == "deg" else 4)
    return Fact(
        topic=topic,
        subject=subject,
        value=value,
        unit=unit,
        storey=storey,
        discipline=discipline,
        source=source,
    )


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _unit_of(quantity: str) -> str:
    return "m3" if quantity.endswith("Volume") else "m2" if quantity.endswith("Area") else "m"


def _scale(quantity: str, scales: Mapping[str, float]) -> float:
    unit = _unit_of(quantity)
    return scales["VOLUMEUNIT" if unit == "m3" else "AREAUNIT" if unit == "m2" else "LENGTHUNIT"]


# The project ------------------------------------------------------------------------------


def _project(file: Any, scales: Mapping[str, float]) -> Iterator[Fact]:
    yield _fact("project.schema", "project", file.schema, None, "file schema")
    header = file.header
    for attribute in ("originating_system", "preprocessor_version"):
        if text := getattr(header.file_name, attribute, None):
            yield _fact("project.software", "project", text, None, f"header {attribute}")
    for text in header.file_description.description or ():
        if text:
            yield _fact("project.standard", "project", text, None, "header file_description")
    for application in file.by_type("IfcApplication"):
        developer = application.ApplicationDeveloper
        text = " ".join(
            part
            for part in (
                getattr(developer, "Name", None),
                application.ApplicationFullName,
                application.Version,
            )
            if part
        )
        yield _fact("project.software", "project", text, None, "IfcApplication")
    for entity, key in (
        *((found, "project") for found in file.by_type("IfcProject")),
        *((found, "site") for found in file.by_type("IfcSite")),
        *((found, "building") for found in file.by_type("IfcBuilding")),
    ):
        subject = entity.Name or key
        for attribute in ("Name", "LongName", "Description", "Phase", "ObjectType"):
            if text := getattr(entity, attribute, None):
                yield _fact(f"{key}.{_snake(attribute)}", subject, str(text), None, attribute)
        if address := getattr(entity, "SiteAddress", None) or getattr(
            entity, "BuildingAddress", None
        ):
            yield _fact(f"{key}.address", subject, _address(address), None, "postal address")
        for attribute, topic in (("RefLatitude", "latitude"), ("RefLongitude", "longitude")):
            if (angle := getattr(entity, attribute, None)) is not None:
                degrees = _degrees(angle)
                yield _fact(f"{key}.{topic}", subject, degrees, "deg", attribute)
                dms = "{}° {}' {}\" {}".format(*[*angle, 0, 0, 0][:4])  # as the file writes it
                yield _fact(f"{key}.{topic}_dms", subject, dms, None, attribute)
        if (height := getattr(entity, "RefElevation", None)) is not None:
            elevation = height * scales["LENGTHUNIT"]
            yield _fact(f"{key}.elevation", subject, elevation, "m", "RefElevation")
        for quantity, value in _quantities(entity).items():
            yield _fact(
                f"{key}.{_snake(quantity)}",
                subject,
                value * _scale(quantity, scales),
                _unit_of(quantity),
                f"Qto {quantity}",
            )


def _address(address: Any) -> str:
    lines = [*(getattr(address, "AddressLines", None) or ())]
    for attribute in ("PostalCode", "Town", "Region", "Country"):
        if text := getattr(address, attribute, None):
            lines.append(text)
    return ", ".join(lines)


def _degrees(angle: Sequence[int]) -> float:
    """IfcCompoundPlaneAngleMeasure: degrees, minutes, seconds, millionths, all of one sign."""
    parts = [*angle, 0, 0, 0][:4]
    return parts[0] + parts[1] / 60 + parts[2] / 3600 + parts[3] / 3_600_000_000


# Storeys ----------------------------------------------------------------------------------


def _storeys(file: Any, scales: Mapping[str, float]) -> Iterator[Fact]:
    storeys = [storey for storey in file.by_type("IfcBuildingStorey") if storey.Name]
    yield _fact("storey.count", "all", len(storeys), "count", "IfcBuildingStorey")
    length = scales["LENGTHUNIT"]
    placed = sorted(
        (storey.Elevation * length, storey.Name)
        for storey in storeys
        if storey.Elevation is not None
    )
    for (elevation, name), above in zip(placed, [*placed[1:], None], strict=False):
        yield _fact("storey.elevation", name, elevation, "m", "Elevation", storey=name)
        if above is not None:
            height = above[0] - elevation
            yield _fact("storey.height", name, height, "m", "next Elevation", storey=name)
    for storey in storeys:
        if storey.LongName:
            yield _fact(
                "storey.long_name", storey.Name, storey.LongName, None, "LongName", storey.Name
            )
        for quantity, value in _quantities(storey).items():
            yield _fact(
                f"storey.{_snake(quantity)}",
                storey.Name,
                value * _scale(quantity, scales),
                _unit_of(quantity),
                f"Qto {quantity}",
                storey=storey.Name,
            )


# Spaces -----------------------------------------------------------------------------------


def _spaces(file: Any, scales: Mapping[str, float]) -> Iterator[Fact]:
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    sums: dict[tuple[str, str, str | None], float] = defaultdict(float)  # topic, subject, storey
    storeys: set[str] = set()
    for entity in file.by_type("IfcSpace"):
        found = _storey(entity)
        storey = None if found is None else found.Name
        if storey is not None:
            storeys.add(storey)
        name = entity.Name or entity.LongName or entity.GlobalId
        function = entity.LongName or entity.Name or "unnamed"
        for where in {None, storey}:
            for key in (("space.count", "all", where), ("space_function.count", function, where)):
                sums[key] += 1
        if entity.LongName:
            yield _fact("space.long_name", name, entity.LongName, None, "LongName", storey)
        if (kind := element_util.get_type(entity)) is not None and kind.Name:
            yield _fact("space.type", name, kind.Name, None, "IfcSpaceType", storey)
        quantities = _quantities(entity)
        body = None if "Height" in quantities else _extrusion(entity)
        if body is not None and abs(body.ExtrudedDirection.DirectionRatios[-1]) > 0.99:  # upright
            height = body.Depth * scales["LENGTHUNIT"]
            yield _fact("space.height", name, height, "m", "body extrusion depth", storey)
        for quantity in SPACE_QUANTITIES:
            if quantity not in quantities:
                continue
            value = quantities[quantity] * _scale(quantity, scales)
            topic = f"space.{_snake(quantity)}"
            yield _fact(topic, name, value, _unit_of(quantity), f"Qto {quantity}", storey)
            if quantity in SPACE_SUMS:
                for where in {None, storey}:
                    sums[(topic, "all", where)] += value
                    sums[(f"space_function.{_snake(quantity)}", function, where)] += value
        solid = _solid(entity, settings)  # objects.py's room area: the solid's footprint
        if solid is not None and solid.footprint.area:
            area = round(solid.footprint.area, 4)
            yield _fact("space.area", name, area, "m2", "geometry footprint (objects.py)", storey)
            for where in {None, storey}:
                sums[("space.area", "all", where)] += area
                sums[("space_function.area", function, where)] += area
        stated = _stated_area(entity)
        if stated is not None:
            area = stated[0] * scales["AREAUNIT"]
            yield _fact("space.stated_area", name, area, "m2", stated[1], storey)
            for where in {None, storey}:
                sums[("space.stated_area", "all", where)] += area
                sums[("space_function.stated_area", function, where)] += area
    for (topic, subject, storey), value in sums.items():
        unit = "count" if topic.endswith(".count") else _unit_of(topic.title().replace("_", ""))
        total = int(value) if unit == "count" else value
        yield _fact(topic, subject, total, unit, "sum over spaces", storey)
        if unit == "count":
            continue
        entity = topic.split(".")[0]
        if (count := sums[(f"{entity}.count", subject, storey)]) > 1:
            yield _fact(f"{topic}.average", subject, value / count, unit, "average", storey)
        if (topic, subject, storey) == (topic, "all", None) and storeys:
            per_storey = value / len(storeys)
            yield _fact(f"{topic}.per_storey", "all", per_storey, unit, "total / storeys")


def _stated_area(space: Any) -> tuple[float, str] | None:
    """The area the authoring tool states for a space, and where it states it."""
    for pset, properties in element_util.get_psets(space, psets_only=True).items():
        for name, value in _flat(properties).items():
            if name in STATED_AREAS and isinstance(value, int | float) and value > 0:
                return float(value), f"{pset}.{name}"
    return None


def _flat(properties: Mapping[str, Any]) -> dict[str, Any]:
    """A property set's values, with those of its complex properties, by name."""
    flat: dict[str, Any] = {}
    for name, value in properties.items():
        if isinstance(value, dict):
            flat.update(_flat(value.get("properties", {})))
        elif name != "id":
            flat[name] = value
    return flat


# Elements ---------------------------------------------------------------------------------


def _quantities(entity: Any) -> dict[str, float]:
    """The numeric quantities of all the entity's Qto sets, by name, in the file's units."""
    return {
        name: float(value)
        for quantities in element_util.get_psets(entity, qtos_only=True).values()
        for name, value in quantities.items()
        if isinstance(value, int | float) and not isinstance(value, bool) and name != "id"
    }


def _element(entity: Any, key: str, scales: Mapping[str, float]) -> _Element:
    kind = element_util.get_type(entity)
    object_type = getattr(entity, "ObjectType", None) or ""
    type_name = (
        (kind.Name if kind is not None else None)
        or REVIT_ID.sub("", object_type)
        or REVIT_ID.sub("", entity.Name or "")
        or entity.is_a()
    )
    stated = _quantities(entity)
    measures = {name: stated[name] * _scale(name, scales) for name in QUANTITIES if name in stated}
    if measures.get("GrossVolume", 0) > GROSS_VOLUME_SANE * measures.get("NetVolume", float("inf")):
        del measures["GrossVolume"]
    psets = element_util.get_psets(entity, psets_only=True)
    for pset, properties in psets.items():  # what the file states without a Qto set
        for name in DIMENSIONS if pset in DIMENSION_SETS else ():
            value = properties.get(name)
            if isinstance(value, int | float) and not isinstance(value, bool):
                measures.setdefault(name, value * _scale(name, scales))
    for attribute, name in (("OverallWidth", "Width"), ("OverallHeight", "Height")):
        if (value := getattr(entity, attribute, None)) is not None:
            measures[name] = value * scales["LENGTHUNIT"]
    for attribute in ("NominalDiameter", "BarLength"):
        value = getattr(entity, attribute, None)
        if value is None and kind is not None:
            value = getattr(kind, attribute, None)
        if value is not None:
            measures[attribute] = value * scales["LENGTHUNIT"]
    extrusion = _extrusion(entity) if key in SLABBED | EXTRUDED else None
    if extrusion is not None and key in EXTRUDED:
        measures.update(_profile(extrusion.SweptArea, scales["LENGTHUNIT"]))
    layers = _layers(entity, scales["LENGTHUNIT"])
    thickness = sum(width for _, width in layers) if layers else None
    if not thickness and key in LAYERED:
        thickness = measures.get("Width")
    if not thickness and key in SLABBED:
        thickness = measures.get("Depth", measures.get("Width"))
        if thickness is None and extrusion is not None:
            thickness = extrusion.Depth * scales["LENGTHUNIT"]
    common = {
        name: value
        for pset, properties in psets.items()
        if pset.startswith("Pset_") and pset.endswith("Common")
        for name, value in properties.items()
    }
    flags = {
        name: common[name]
        for name in ("IsExternal", "LoadBearing")
        if isinstance(common.get(name), bool)
    }
    rating = common.get("FireRating")
    storey = _storey(entity)
    predefined = getattr(entity, "PredefinedType", None)
    if predefined in (None, "NOTDEFINED", "USERDEFINED") and kind is not None:
        predefined = getattr(kind, "PredefinedType", None) or predefined
    return _Element(
        name=entity.Name or entity.GlobalId,
        type_name=type_name,
        group_name=REVIT_ID.sub("", entity.Name or "") or f"Unnamed {entity.is_a()[3:]}",
        family_name=_family(entity.Name or "", object_type, type_name),
        storey=None if storey is None else storey.Name,
        predefined=predefined,
        measures=measures,
        layers=layers,
        materials=tuple(
            material.Name
            for material in element_util.get_materials(entity)
            if material is not None and material.Name
        ),
        thickness=thickness,
        flags=flags,
        fire_rating=str(rating) if rating not in (None, "") else None,
        global_id=entity.GlobalId,
    )


def _family(name: str, object_type: str, type_name: str) -> str:
    """Revit's "Family:Type": its ObjectType (newer exports), else its Name less the type
    and the id ("Single-Flush:36 x 84:36 x 84:140762", IFC2x3 exports), else the type."""
    family = REVIT_ID.sub("", object_type)
    if ":" in family:
        return family
    name = REVIT_ID.sub("", name)
    family = name.removesuffix(f":{type_name}")
    return family if family != name and ":" in family else type_name


def _layers(entity: Any, length: float) -> tuple[tuple[str, float], ...]:
    """The material layers: of its layer set, else the layer quantities Revit writes (an
    IfcPhysicalComplexQuantity per material, with its Width)."""
    found = element_util.get_material(entity, should_skip_usage=True)
    if found is not None and found.is_a("IfcMaterialLayerSet"):
        return tuple(
            ((layer.Material.Name if layer.Material else "") or "", layer.LayerThickness * length)
            for layer in found.MaterialLayers
        )
    return tuple(
        (name, value["properties"]["Width"] * length)
        for quantities in element_util.get_psets(entity, qtos_only=True).values()
        for name, value in quantities.items()
        if isinstance(value, dict)
        and value.get("Discrimination") == "Layer"
        and isinstance(value.get("properties", {}).get("Width"), int | float)
    )


def _extrusion(entity: Any) -> Any | None:
    """The first extruded solid of the entity's body, through mapped items and booleans."""
    shape = getattr(entity, "Representation", None)
    items = [
        item
        for representation in (shape.Representations if shape else ())
        if representation.RepresentationIdentifier in ("Body", None)
        for item in representation.Items
    ]
    for _ in range(MAX_NESTING):
        for item in items:
            if item.is_a("IfcExtrudedAreaSolid"):
                return item
        items = [
            inner
            for item in items
            for inner in (
                item.MappingSource.MappedRepresentation.Items
                if item.is_a("IfcMappedItem")
                else (item.FirstOperand,)
                if item.is_a("IfcBooleanResult")
                else ()
            )
        ]
    return None


def _profile(profile: Any, length: float) -> dict[str, float]:
    """A section's width and depth (a rectangle, an I or a T), or its diameter (a circle)."""
    if profile.is_a("IfcCircleProfileDef"):
        return {"ProfileDiameter": 2 * profile.Radius * length}
    for width, depth in (
        ("XDim", "YDim"),
        ("OverallWidth", "OverallDepth"),
        ("FlangeWidth", "Depth"),
    ):
        if getattr(profile, width, None) and getattr(profile, depth, None):
            return {
                "ProfileWidth": getattr(profile, width) * length,
                "ProfileDepth": getattr(profile, depth) * length,
            }
    if profile.is_a("IfcArbitraryClosedProfileDef"):  # its outline's bounding box
        points = [
            point
            for item in profile.file.traverse(profile.OuterCurve)
            for point in (
                [item.Coordinates]
                if item.is_a("IfcCartesianPoint")
                else item.CoordList
                if item.is_a("IfcCartesianPointList")
                else []
            )
        ]
        if points:
            xs, ys = [point[0] for point in points], [point[1] for point in points]
            return {
                "ProfileWidth": (max(xs) - min(xs)) * length,
                "ProfileDepth": (max(ys) - min(ys)) * length,
            }
    return {}


def _grouped(elements: Sequence[_Element], field: str) -> dict[str, list[_Element]]:
    groups: dict[str, list[_Element]] = defaultdict(list)
    for element in elements:
        groups[getattr(element, field)].append(element)
    return dict(groups)


def _parts(elements: Sequence[_Element]) -> Iterator[tuple[str, list[_Element]]]:
    """The parts of a class one sum is given for."""
    yield "all", list(elements)
    for flag, yes, no in (
        ("IsExternal", "external", "internal"),
        ("LoadBearing", "load_bearing", "non_load_bearing"),
    ):
        if any(flag in element.flags for element in elements):
            yield yes, [element for element in elements if element.flags.get(flag) is True]
            yield no, [element for element in elements if element.flags.get(flag) is False]
    for predefined in sorted({element.predefined for element in elements if element.predefined}):
        yield f"predefined:{predefined}", [e for e in elements if e.predefined == predefined]


def _totals(
    topic: str, subject: str, group: Sequence[_Element], discipline: Discipline, storey: str | None
) -> Iterator[Fact]:
    yield _fact(f"{topic}.count", subject, len(group), "count", "count", storey, discipline)
    for name in (*(name for name, summed in QUANTITIES.items() if summed), "BarLength"):
        values = [element.measures[name] for element in group if name in element.measures]
        if values:
            yield _fact(
                f"{topic}.{_snake(name)}",
                subject,
                sum(values),
                _unit_of(name),
                f"sum of Qto {name} over {len(values)}",
                storey,
                discipline,
            )


def _sums(
    key: str,
    discipline: Discipline,
    elements: Sequence[_Element],
    field: str = "type_name",
    by_storey: bool = True,
) -> Iterator[Fact]:
    """`key` "wall": the class's parts ("wall.*") and its types ("wall_type.*"), in the whole
    building and per storey. `key` "wall_name", `field` "group_name": its groups of one name,
    in each part of the class."""
    storeys = sorted({e.storey for e in elements if e.storey}) if by_storey else []
    for storey in (None, *storeys):
        chosen = [e for e in elements if storey is None or e.storey == storey]
        topic = f"{key}_type" if field == "type_name" else key
        if field == "type_name":
            for subject, group in _parts(chosen):
                yield from _totals(key, subject, group, discipline, storey)
        for name, group in _grouped(chosen, field).items():
            yield from _totals(topic, name, group, discipline, storey)
        if storey is not None:
            continue
        for part, in_part in _parts(chosen):  # e.g. "Brick 300 | external"
            if part != "all" and not part.startswith("predefined:"):
                for name, group in _grouped(in_part, field).items():
                    yield from _totals(topic, f"{name} | {part}", group, discipline, None)


def _distributions(
    key: str, discipline: Discipline, elements: Sequence[_Element]
) -> Iterator[Fact]:
    """How many elements have each size, width or thickness ("900 x 2100 mm", "240 mm")."""

    def mm(value: float) -> str:
        return f"{value * 1000:.0f}"

    counted: dict[tuple[str, str], int] = defaultdict(int)
    for e in elements:
        width, height = e.measures.get("Width"), e.measures.get("Height")
        if key in ("door", "window") and width and height:
            counted[(f"{key}_size", f"{mm(width)} x {mm(height)} mm")] += 1
            counted[(f"{key}_width", f"{mm(width)} mm")] += 1
        if e.thickness:
            counted[(f"{key}_thickness", f"{mm(e.thickness)} mm")] += 1
    for (topic, subject), count in counted.items():
        yield _fact(f"{topic}.count", subject, count, "count", "count", None, discipline)


def _types(
    topic: str, discipline: Discipline, groups: Mapping[str, Sequence[_Element]]
) -> Iterator[Fact]:
    """What a type (or a group of one name) is, over all its elements: each value once."""
    for type_name, group in groups.items():

        def listed(
            name: str,
            values: Iterable[Any],
            unit: str | None,
            source: str,
            subject: str = type_name,
        ) -> Iterator[Fact]:
            for value in sorted({v for v in values if v is not None}, key=str):
                yield _fact(f"{topic}.{name}", subject, value, unit, source, None, discipline)

        yield from listed(
            "thickness",
            (None if e.thickness is None else round(e.thickness, 4) for e in group),
            "m",
            "material layers, else Qto",
        )
        for name, summed in QUANTITIES.items():
            if not summed:
                values = (e.measures.get(name) for e in group)
                rounded = (None if v is None else round(v, 4) for v in values)
                yield from listed(_snake(name), rounded, _unit_of(name), f"Qto/attribute {name}")
        diameters = (e.measures.get("NominalDiameter") for e in group)
        yield from listed("diameter", diameters, "m", "NominalDiameter")
        yield from listed("material", (m for e in group for m in e.materials), None, "material")
        yield from listed("predefined_type", (e.predefined for e in group), None, "PredefinedType")
        yield from listed("fire_rating", (e.fire_rating for e in group), None, "Pset FireRating")
        layers = {e.layers for e in group if e.layers}
        for layers_of_one in sorted(layers):
            for number, (material, width) in enumerate(layers_of_one, start=1):
                yield _fact(
                    f"{topic}.layer",
                    f"{type_name} | layer {number} | {material}",
                    round(width, 4),
                    "m",
                    "material layer",
                    None,
                    discipline,
                )
        rated = sum(e.fire_rating is not None for e in group)
        if rated:
            yield _fact(
                f"{topic}.fire_rated_count",
                type_name,
                rated,
                "count",
                "Pset FireRating",
                None,
                discipline,
            )


def _one_by_one(key: str, discipline: Discipline, elements: Sequence[_Element]) -> Iterator[Fact]:
    for e in elements:

        def fact(
            name: str, value: float | int | str, unit: str | None, source: str, e: _Element = e
        ) -> Fact:
            return _fact(f"{key}.{name}", e.name, value, unit, source, e.storey, discipline)

        yield fact("global_id", e.global_id, None, "GlobalId")
        for name in dict.fromkeys((e.type_name, e.family_name)):
            yield fact("type", name, None, "type name")
        for name, value in e.measures.items():
            yield fact(_snake(name), value, _unit_of(name), f"Qto/attribute {name}")
        if e.thickness is not None:
            yield fact("thickness", e.thickness, "m", "material layers, else Qto")
        if e.predefined:
            yield fact("predefined_type", e.predefined, None, "PredefinedType")
        for material in dict.fromkeys(e.materials):
            yield fact("material", material, None, "material")
        if e.fire_rating:
            yield fact("fire_rating", e.fire_rating, None, "Pset FireRating")
        for flag, name in (("IsExternal", "is_external"), ("LoadBearing", "load_bearing")):
            if flag in e.flags:
                yield fact(name, str(e.flags[flag]).lower(), None, f"Pset {flag}")


def _material_volumes(element: _Element) -> Iterator[tuple[str, float]]:
    """An element's volume per material: split by layer thickness, or all of it for an element
    of one material. Nothing for one of several materials without layers."""
    volume = _volume(element)
    if not volume:
        return
    total = sum(width for _, width in element.layers)
    if element.layers and total > 0:
        for material, width in element.layers:
            yield material, volume * width / total
    elif len(set(element.materials)) == 1:
        yield element.materials[0], volume


def _volume(element: _Element) -> float | None:
    """The element's volume as the file states it: NetVolume, else GrossVolume, else Volume."""
    return next(
        (
            element.measures[name]
            for name in ("NetVolume", "GrossVolume", "Volume")
            if name in element.measures
        ),
        None,
    )


def _kind(material: str) -> str | None:
    return next((kind for kind, words in MATERIAL_KINDS.items() if words.search(material)), None)


# Derived numbers -------------------------------------------------------------------------


def _stats(key: str, discipline: Discipline, elements: Sequence[_Element]) -> Iterator[Fact]:
    """Smallest, largest and average of each measure over each part of the class, and the
    totals per storey (over the storeys that hold the class)."""
    for subject, group in _parts(elements):
        for name in (*QUANTITIES, "Thickness"):
            values = [
                v
                for e in group
                if (v := e.thickness if name == "Thickness" else e.measures.get(name))
            ]
            if len(values) < 2:
                continue
            for stat, value in (
                ("min", min(values)),
                ("max", max(values)),
                ("average", sum(values) / len(values)),
            ):
                yield _fact(
                    f"{key}.{_snake(name)}.{stat}",
                    subject,
                    value,
                    _unit_of(name),
                    f"{stat} of {name} over {len(values)}",
                    None,
                    discipline,
                )
    storeys = {e.storey for e in elements if e.storey}
    if not storeys:
        return
    for fact in _totals(key, "all", elements, discipline, None):
        yield fact.model_copy(
            update={
                "topic": f"{fact.topic}.per_storey",
                "value": round(fact.value / len(storeys), 4),  # type: ignore[operator]
                "unit": fact.unit,
                "source": f"{fact.source} / {len(storeys)} storeys",
            }
        )


def _by_material(
    key: str,
    discipline: Discipline,
    elements: Sequence[_Element],
    splits: Sequence[str] = ("by_material", "by_material_kind"),
) -> Iterator[Fact]:
    """How many of the class's elements have each material (or kind of material), and their
    volume of it (split by layer thickness)."""
    for split in splits:
        group_of = _kind if split == "by_material_kind" else lambda material: material
        counts: dict[str, int] = defaultdict(int)
        volumes: dict[str, float] = defaultdict(float)
        for e in elements:
            for group in {group_of(m) for m in e.materials} - {None}:
                counts[group] += 1  # type: ignore[index]
            for material, volume in _material_volumes(e):
                if (group := group_of(material)) is not None:
                    volumes[group] += volume
        for group, count in counts.items():
            yield _fact(f"{key}.count.{split}", group, count, "count", "count", None, discipline)
        for group, volume in volumes.items():
            yield _fact(
                f"{key}.volume.{split}",
                group,
                volume,
                "m3",
                "volume by layer thickness",
                None,
                discipline,
            )


def _structural(by_key: Mapping[str, Sequence[_Element]]) -> Iterator[Fact]:
    """The structural elements: the STRUCTURAL classes, and the walls unless the file states
    them non-load-bearing (no wall at all when no wall states it)."""
    walls = by_key.get("wall", ())
    stated = any("LoadBearing" in w.flags for w in walls)
    bearing = [w for w in walls if stated and w.flags.get("LoadBearing") is not False]
    elements = [*(e for key in STRUCTURAL for e in by_key.get(key, ())), *bearing]
    for storey in (None, *sorted({e.storey for e in elements if e.storey})):
        count = sum(storey is None or e.storey == storey for e in elements)
        source = f"{' + '.join(STRUCTURAL)} + {len(bearing)} bearing walls"
        yield _fact("structural.count.total", "all", count, "count", source, storey, "structural")


def _foundation(by_key: Mapping[str, Sequence[_Element]]) -> Iterator[Fact]:
    found = {
        key: [
            e
            for e in by_key.get(key, ())
            if key in ("footing", "pile")
            or e.predefined == "BASESLAB"
            or FOUNDATION.search(e.type_name)
        ]
        for key in FOUNDATION_CLASSES
    }
    for subject, group in (
        ("all", [e for elements in found.values() for e in elements]),
        *found.items(),
    ):
        if group:
            for fact in _totals("foundation", subject, group, "structural", None):
                yield fact.model_copy(update={"topic": f"{fact.topic}.total"})
