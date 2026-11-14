"""Synthetic IFC building models and SVG sheet twins for the tests, built with ifcopenshell: no
partner data in the repo.

`IfcFile` writes only what the reader looks at: units, storeys, objects with their containment,
decomposition and Qto quantities, and spaces with a solid. Lengths are given in metres and
written in the file's unit; quantities are written as given, in the file's units.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal
from xml.sax.saxutils import quoteattr

import ifcopenshell
import ifcopenshell.guid

Point = tuple[float, float]
Schema = Literal["IFC4", "IFC2X3"]
QUANTITY_KINDS = ("Length", "Area", "Volume")  # IfcQuantityLength, ... by the name's ending


def box(x0: float, y0: float, x1: float, y1: float) -> list[Point]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


class IfcFile:
    """One model under construction. Every method that adds an object returns its GlobalId."""

    def __init__(
        self, schema: Schema = "IFC4", millimetres: bool = False, area_units: bool = True
    ) -> None:
        """`area_units` False: the file names only its length unit."""
        self._file: Any = ifcopenshell.file(schema=schema)
        self._per_metre = 1000.0 if millimetres else 1.0
        units = [self._new("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")]
        if millimetres:
            units[0].Prefix = "MILLI"
        if area_units:
            units += [
                self._new("IfcSIUnit", UnitType="AREAUNIT", Name="SQUARE_METRE"),
                self._new("IfcSIUnit", UnitType="VOLUMEUNIT", Name="CUBIC_METRE"),
            ]
        self._origin = self._placement(0.0)
        self._context = self._new(
            "IfcGeometricRepresentationContext",
            ContextType="Model",
            CoordinateSpaceDimension=3,
            Precision=1e-5,
            WorldCoordinateSystem=self._origin,
        )
        self._project = self._rooted(
            "IfcProject",
            Name="Demo house",
            UnitsInContext=self._new("IfcUnitAssignment", Units=units),
            RepresentationContexts=[self._context],
        )

    def storey(self, name: str) -> str:
        storey = self._rooted("IfcBuildingStorey", Name=name)
        self._rooted("IfcRelAggregates", RelatingObject=self._project, RelatedObjects=[storey])
        return storey.GlobalId

    def element(
        self,
        ifc_class: str,
        *,
        storey: str | None = None,
        part_of: str | None = None,
        name: str | None = None,
        quantities: Mapping[str, float] | None = None,
    ) -> str:
        """An object contained in `storey`, or a part of the object `part_of` (both by GlobalId).
        `quantities`: by the file's quantity name, e.g. NetSideArea, in one Qto set."""
        element = self._rooted(ifc_class, Name=name)
        if storey is not None:
            self._rooted(
                "IfcRelContainedInSpatialStructure",
                RelatingStructure=self._file.by_guid(storey),
                RelatedElements=[element],
            )
        if part_of is not None:
            self._part(part_of, element)
        if quantities:
            stated = [
                self._new(f"IfcQuantity{kind}", Name=quantity, **{f"{kind}Value": float(value)})
                for quantity, value in quantities.items()
                for kind in QUANTITY_KINDS
                if quantity.endswith(kind)
            ]
            self._rooted(
                "IfcRelDefinesByProperties",
                RelatedObjects=[element],
                RelatingPropertyDefinition=self._rooted(
                    "IfcElementQuantity", Name="Qto_BaseQuantities", Quantities=stated
                ),
            )
        return element.GlobalId

    def space(
        self,
        storey: str,
        number: str,
        name: str,
        *solids: tuple[Sequence[Point], float, float],
    ) -> str:
        """A room of `storey`. Each solid is an outline in metres, the height of its floor and
        its own height; without one the space has no geometry."""
        space = self._rooted(
            "IfcSpace",
            Name=number,
            LongName=name,
            ObjectPlacement=self._new("IfcLocalPlacement", RelativePlacement=self._origin),
            Representation=self._body(solids) if solids else None,
        )
        self._part(storey, space)
        return space.GlobalId

    def _body(self, solids: Sequence[tuple[Sequence[Point], float, float]]) -> Any:
        bodies = [
            self._new(
                "IfcExtrudedAreaSolid",
                SweptArea=self._new(
                    "IfcArbitraryClosedProfileDef",
                    ProfileType="AREA",
                    OuterCurve=self._new(
                        "IfcPolyline",
                        Points=[self._point(x, y) for x, y in (*outline, outline[0])],
                    ),
                ),
                Position=self._placement(floor),
                ExtrudedDirection=self._new("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)),
                Depth=height * self._per_metre,
            )
            for outline, floor, height in solids
        ]
        return self._new(
            "IfcProductDefinitionShape",
            Representations=[
                self._new(
                    "IfcShapeRepresentation",
                    ContextOfItems=self._context,
                    RepresentationIdentifier="Body",
                    RepresentationType="SweptSolid",
                    Items=bodies,
                )
            ],
        )

    def window(
        self,
        storey: str,
        name: str,
        *,
        solid: tuple[Sequence[Point], float, float] | None = None,
        at: tuple[float, float, float] | None = None,
        height: float | None = None,
    ) -> str:
        """A window of `storey`. `solid`: its shape, as a space's (outline, floor, height);
        without one the geometry kernel has nothing to build. `at`: where it is placed, in
        metres; `height`: its stated OverallHeight."""
        placed = self._origin
        if at is not None:
            placed = self._new("IfcAxis2Placement3D", Location=self._point(*at))
        window = self._rooted(
            "IfcWindow",
            Name=name,
            ObjectPlacement=self._new("IfcLocalPlacement", RelativePlacement=placed)
            if solid is not None or at is not None
            else None,
            Representation=None if solid is None else self._body([solid]),
            OverallHeight=None if height is None else height * self._per_metre,
        )
        self._rooted(
            "IfcRelContainedInSpatialStructure",
            RelatingStructure=self._file.by_guid(storey),
            RelatedElements=[window],
        )
        return window.GlobalId

    def boundary(self, space: str, element: str) -> None:
        """The model's own statement that `element` bounds `space` (IfcRelSpaceBoundary)."""
        self._rooted(
            "IfcRelSpaceBoundary",
            RelatingSpace=self._file.by_guid(space),
            RelatedBuildingElement=self._file.by_guid(element),
            PhysicalOrVirtualBoundary="PHYSICAL",
            InternalOrExternalBoundary="EXTERNAL",
        )

    def ifc(self) -> bytes:
        return self._file.to_string().encode()

    def _new(self, kind: str, **attrs: Any) -> Any:
        return self._file.create_entity(kind, **attrs)

    def _rooted(self, kind: str, **attrs: Any) -> Any:
        return self._new(kind, GlobalId=ifcopenshell.guid.new(), **attrs)

    def _part(self, whole: str, part: Any) -> None:
        self._rooted(
            "IfcRelAggregates", RelatingObject=self._file.by_guid(whole), RelatedObjects=[part]
        )

    def _point(self, *metres: float) -> Any:
        return self._new(
            "IfcCartesianPoint", Coordinates=tuple(value * self._per_metre for value in metres)
        )

    def _placement(self, height: float) -> Any:
        return self._new("IfcAxis2Placement3D", Location=self._point(0.0, 0.0, height))


@dataclass(frozen=True)
class Shape:
    """One object's group of a sheet twin: closed rings of SVG points, and round parts as
    (cx, cy, r). `d`: path data given as written, for the commands a ring cannot say."""

    ifc_class: str
    guid: str | None
    rings: Sequence[Sequence[Point]] = ()
    circles: Sequence[tuple[float, float, float]] = ()
    name: str | None = None
    cut: bool = False
    d: str | None = None


def sheet_svg(
    width: float,
    height: float,
    shapes: Sequence[Shape],
    texts: Sequence[tuple[float, float, str]] = (),
) -> bytes:
    """The twin of a sheet as IfcConvert writes one: a group per object, one path for its rings."""
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:g} {height:g}">']
    for shape in shapes:
        d = shape.d or " ".join(
            "M" + " L".join(f"{x:g},{y:g}" for x, y in ring) + " Z" for ring in shape.rings
        )
        attrs = f"class={quoteattr(('cut ' if shape.cut else '') + shape.ifc_class)}"
        if shape.guid is not None:
            attrs += f" data-guid={quoteattr(shape.guid)}"
        if shape.name is not None:
            attrs += f" data-name={quoteattr(shape.name)}"
        lines.append(f"<g {attrs}>")
        if d:
            lines.append(f'<path d="{d}"/>')
        lines += [f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}"/>' for cx, cy, r in shape.circles]
        lines.append("</g>")
    lines += [f'<text x="{x:g}" y="{y:g}"><tspan>{text}</tspan></text>' for x, y, text in texts]
    return "\n".join([*lines, "</svg>"]).encode()
