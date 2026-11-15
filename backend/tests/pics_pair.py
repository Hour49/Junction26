"""A plan and the discipline pictures of the same floor, for the plan-edit follow on pictures
(.agents brief pics-edit-follow W4; spec services-follow.md § Pictures).

One small IFC (metres): tests/swiss_walls.py's flat (Bagno 1.01 | a 0.12 m wall at x 3..3.12
with a 1 m door at y 1..2 | Stanza 1.02, 0.2 m outer walls), Floor 1 with heating (a radiator
on each side of the inside wall, one in Bagno's corner, a supply pipe crossing the wall) and
plumbing (a cold-water pipe inside the wall, a washbasin), Floor 2 with heating elsewhere: the
other-floor distractor. The bench renderer (plan_picture.render_model) draws the pictures; the
plan is a vector PDF (the only plan the no-keys backend reads walls from) on the same frame in
metres as the pictures, so a pairing by file names lays them over page to page.

`pair_zip()` gives the upload: `set/A-101 Floor 1 plan.pdf`, `set/H-101 Floor 1 heating.png`,
`set/P-101 Floor 1 plumbing.png`, `set/H-102 Floor 2 heating.png`.
"""

import io
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.guid
from pdf_sheets import BLACK, SheetPdf, rect
from swiss_walls import WALL
from test_vector_pdf import swiss_room

from app.adapters.ifc_model.plan_picture import render_model

PT_PER_M = 72 / 25.4 * 1000 / 100  # the plan PDF is at 1:100
INSIDE = (3.0, 3.12)  # the wall between Bagno 1.01 and Stanza 1.02, x in metres
DOOR = (1.0, 2.0)  # its door, y in metres
END = 3.12 + 3.888
# (x0, y0, x1, y1) in metres, y up: façades, then the inside wall either side of the door
WALLS = [
    (-0.2, 3.0, END + 0.2, 3.2),
    (-0.2, -0.2, END + 0.2, 0.0),
    (-0.2, 0.0, 0.0, 3.0),
    (END, 0.0, END + 0.2, 3.0),
    (INSIDE[0], 0.0, INSIDE[1], DOOR[0]),
    (INSIDE[0], DOOR[1], INSIDE[1], 3.0),
]
ROOMS = [
    ((0.0, 0.0, 3.0, 3.0), ("Bagno", "1.01", "9.00 m²")),
    ((3.12, 0.0, END, 3.0), ("Stanza", "1.02", "11.66 m²")),
]
FLOORS = {"Floor 1": 0.0, "Floor 2": 3000.0}  # storey -> elevation in mm


class _Model:
    """A model in millimetres: storeys, walls, box terminals and extruded pipes."""

    def __init__(self) -> None:
        self.f: Any = ifcopenshell.file(schema="IFC4")
        mm = self.f.createIfcSIUnit(UnitType="LENGTHUNIT", Prefix="MILLI", Name="METRE")
        self.context = self.f.createIfcGeometricRepresentationContext(
            ContextType="Model",
            CoordinateSpaceDimension=3,
            Precision=1e-5,
            WorldCoordinateSystem=self._axes((0.0, 0.0, 0.0)),
        )
        project = self._new(
            "IfcProject",
            Name="pics-pair",
            UnitsInContext=self.f.createIfcUnitAssignment([mm]),
            RepresentationContexts=[self.context],
        )
        self.storeys = {
            name: self._new(
                "IfcBuildingStorey",
                Name=name,
                Elevation=z,
                ObjectPlacement=self.f.createIfcLocalPlacement(None, self._axes((0.0, 0.0, z))),
            )
            for name, z in FLOORS.items()
        }
        self._new(
            "IfcRelAggregates", RelatingObject=project, RelatedObjects=list(self.storeys.values())
        )
        self.contained: dict[str, list[Any]] = {name: [] for name in FLOORS}

    def _new(self, ifc_class: str, **attrs: Any) -> Any:
        return self.f.create_entity(ifc_class, GlobalId=ifcopenshell.guid.new(), **attrs)

    def _axes(self, at: tuple[float, ...], axis: Any = None, ref: Any = None) -> Any:
        direction = self.f.createIfcDirection
        return self.f.createIfcAxis2Placement3D(
            self.f.createIfcCartesianPoint(at),
            direction(axis) if axis else None,
            direction(ref) if ref else None,
        )

    def _box(self, dx: float, dy: float, dz: float, z: float = 0.0) -> Any:
        profile = self.f.createIfcRectangleProfileDef("AREA", None, None, dx * 1000, dy * 1000)
        return self.f.createIfcExtrudedAreaSolid(
            profile, self._axes((0.0, 0.0, z * 1000)), self.f.createIfcDirection((0, 0, 1)), dz
        )

    def _element(self, storey: str, ifc_class: str, at: tuple[float, float], solid: Any) -> Any:
        shape = self.f.createIfcShapeRepresentation(self.context, "Body", "SweptSolid", [solid])
        element = self._new(
            ifc_class,
            Name=ifc_class,
            ObjectPlacement=self.f.createIfcLocalPlacement(
                self.storeys[storey].ObjectPlacement,
                self._axes((at[0] * 1000, at[1] * 1000, 0.0)),
            ),
            Representation=self.f.createIfcProductDefinitionShape(None, None, [shape]),
        )
        self.contained[storey].append(element)
        return element

    def walls(self, storey: str) -> None:
        for x0, y0, x1, y1 in WALLS:
            centre = ((x0 + x1) / 2, (y0 + y1) / 2)
            self._element(storey, "IfcWall", centre, self._box(x1 - x0, y1 - y0, 3000.0))

    def terminals(
        self, storey: str, ifc_class: str, type_name: str, boxes: list[tuple[float, ...]]
    ) -> None:
        """Boxes (x, y, dx, dy) in metres, centred on (x, y)."""
        elements = [
            self._element(storey, ifc_class, (x, y), self._box(dx, dy, 600.0, z=0.2))
            for x, y, dx, dy in boxes
        ]
        self._new("IfcRelDefinesByType", RelatedObjects=elements,
                  RelatingType=self._new(f"{ifc_class}Type", Name=type_name))  # fmt: skip

    def pipes(
        self, storey: str, system: str, kind: str, runs: list[tuple[float, float, str, float]]
    ) -> None:
        """Runs (start x, start y, "x" or "y", length) in metres, 2.5 m up."""
        disc = self.f.createIfcCircleProfileDef("AREA", None, None, 10.0)
        elements = []
        for x, y, direction, length in runs:
            axis = (1.0, 0.0, 0.0) if direction == "x" else (0.0, 1.0, 0.0)
            solid = self.f.createIfcExtrudedAreaSolid(
                disc,
                self._axes((0.0, 0.0, 2500.0), axis, (0.0, 0.0, 1.0)),
                self.f.createIfcDirection((0, 0, 1)),
                length * 1000,
            )
            pipe = self._element(storey, "IfcPipeSegment", (x, y), solid)
            props = [
                self.f.createIfcPropertySingleValue("Size", None, self.f.createIfcLabel("20 mmø")),
                self.f.createIfcPropertySingleValue(
                    "System Type", None, self.f.createIfcLabel(kind)
                ),
            ]
            self._new(
                "IfcRelDefinesByProperties",
                RelatedObjects=[pipe],
                RelatingPropertyDefinition=self._new(
                    "IfcPropertySet", Name="Mechanical", HasProperties=props
                ),
            )
            elements.append(pipe)
        group = self._new("IfcDistributionSystem", Name=system)
        self._new("IfcRelAssignsToGroup", RelatedObjects=elements, RelatingGroup=group)

    def save(self, path: Path) -> Path:
        for name, elements in self.contained.items():
            self._new(
                "IfcRelContainedInSpatialStructure",
                RelatingStructure=self.storeys[name],
                RelatedElements=elements,
            )
        self.f.write(str(path))
        return path


def pair_model(path: Path) -> Path:
    model = _Model()
    for storey in FLOORS:
        model.walls(storey)
    # Floor 1 heating: one radiator each side of the inside wall (on its strip), one in Bagno's
    # corner, a supply pipe crossing the wall above the door
    radiators = [(2.9, 2.5, 0.1, 0.8), (3.22, 0.5, 0.1, 0.8), (0.3, 0.3, 0.8, 0.1)]
    model.terminals("Floor 1", "IfcSpaceHeater", "Radiator 600", radiators)
    model.pipes("Floor 1", "Heating Supply", "Hydronic Supply", [(1.0, 2.6, "x", 5.0)])
    # Floor 1 plumbing: a cold-water pipe 1 m inside the wall, a washbasin in Bagno
    model.terminals("Floor 1", "IfcSanitaryTerminal", "Washbasin", [(1.0, 2.8, 0.6, 0.4)])
    model.pipes("Floor 1", "Cold Water", "Domestic Cold Water", [(3.06, 2.0, "y", 1.0)])
    # Floor 2 heating, the distractor: radiators on the façades only
    model.terminals("Floor 2", "IfcSpaceHeater", "Radiator 600",
                    [(1.5, 0.15, 0.8, 0.1), (5.0, 0.15, 0.8, 0.1)])  # fmt: skip
    model.pipes("Floor 2", "Heating Supply", "Hydronic Supply", [(1.0, 0.4, "x", 4.5)])
    return model.save(path)


def plan_pdf(truth: dict[str, Any]) -> bytes:
    """The flat's floor plan as a vector PDF at 1:100, on a picture's frame: the same size in
    metres and the same origin, so a point is at the same page fraction on both."""
    k = truth["px_per_m"]
    (ox, oy), (w_px, h_px) = truth["origin_m"], truth["size_px"]
    sheet = SheetPdf(w_px / k * PT_PER_M, h_px / k * PT_PER_M)

    def at(x: float, y: float) -> tuple[float, float]:
        return ((x - ox) * PT_PER_M, (oy - y) * PT_PER_M)

    def box(x0: float, y0: float, x1: float, y1: float) -> tuple[float, float, float, float]:
        (a, b), (c, d) = at(x0, y1), at(x1, y0)
        return (a, b, c, d)

    for room, lines in ROOMS:
        swiss_room(sheet, box(*room), *lines)
    for wall in WALLS:
        sheet.path(rect(*box(*wall)), stroke=BLACK, width=0.99, fill=WALL)
    sheet.text("Massstab 1:100", sheet.width - 150, sheet.height - 20)
    return sheet.pdf()


def pair_zip() -> bytes:
    """The upload: the plan PDF and the three pictures, in one ZIP folder."""
    names = {
        "pics-pair--Floor_1--heating": "H-101 Floor 1 heating.png",
        "pics-pair--Floor_1--plumbing": "P-101 Floor 1 plumbing.png",
        "pics-pair--Floor_2--heating": "H-102 Floor 2 heating.png",
    }
    with tempfile.TemporaryDirectory() as tmp:
        model = pair_model(Path(tmp) / "pics-pair.ifc")
        pictures = render_model(model, Path(tmp), background=model, dpi=100)
        drawn = {p.stem: p for p in pictures}
        assert set(names) <= set(drawn), sorted(drawn)  # the renderer drew every sheet
        truth = json.loads(drawn["pics-pair--Floor_1--heating"].with_suffix(".json").read_text())
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            archive.writestr("set/A-101 Floor 1 plan.pdf", plan_pdf(truth))
            for stem, name in names.items():
                archive.write(drawn[stem], f"set/{name}")
        return out.getvalue()


if __name__ == "__main__":  # python tests/pics_pair.py <out dir>: the zip and the truths
    import sys

    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "pics-pair.zip").write_bytes(pair_zip())
