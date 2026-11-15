"""AC-15 of docs/specs/backend/discipline-pictures.md: the bench renderer on a synthetic model."""

import json
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.guid
import numpy as np
import pytest
from PIL import Image

from app.adapters.ifc_model.facts_mep import mep_facts
from app.adapters.ifc_model.plan_picture import render_model

HEATERS = {"Radiator A": [(1.0, 1.0), (5.0, 1.0), (9.0, 1.0)], "Radiator B": [(5.0, 6.0)]}
# system -> runs (start x, start y, direction, length in m)
PIPES = {
    "Heating Supply": [(0.0, 2.0, "x", 6.0), (6.0, 2.0, "y", 3.5)],
    "Heating Return": [(0.0, 3.0, "x", 4.25)],
}


class _Builder:
    """A model in millimetres, one storey, with box heaters and extruded pipes."""

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
            Name="p",
            UnitsInContext=self.f.createIfcUnitAssignment([mm]),
            RepresentationContexts=[self.context],
        )
        self.storey = self._new(
            "IfcBuildingStorey",
            Name="Level 1",
            Elevation=0.0,
            ObjectPlacement=self.f.createIfcLocalPlacement(None, self._axes((0.0, 0.0, 0.0))),
        )
        self._new("IfcRelAggregates", RelatingObject=project, RelatedObjects=[self.storey])
        self.contained: list[Any] = []

    def _new(self, ifc_class: str, **attrs: Any) -> Any:
        return self.f.create_entity(ifc_class, GlobalId=ifcopenshell.guid.new(), **attrs)

    def _axes(self, at: tuple[float, ...], axis: Any = None, ref: Any = None) -> Any:
        direction = self.f.createIfcDirection
        return self.f.createIfcAxis2Placement3D(
            self.f.createIfcCartesianPoint(at),
            direction(axis) if axis else None,
            direction(ref) if ref else None,
        )

    def _element(self, ifc_class: str, at: tuple[float, float], solid: Any) -> Any:
        shape = self.f.createIfcShapeRepresentation(self.context, "Body", "SweptSolid", [solid])
        element = self._new(
            ifc_class,
            Name=ifc_class,
            ObjectPlacement=self.f.createIfcLocalPlacement(
                self.storey.ObjectPlacement, self._axes((at[0] * 1000, at[1] * 1000, 0.0))
            ),
            Representation=self.f.createIfcProductDefinitionShape(None, None, [shape]),
        )
        self.contained.append(element)
        return element

    def heaters(self, type_name: str, points: list[tuple[float, float]]) -> None:
        box = self.f.createIfcRectangleProfileDef("AREA", None, None, 1000.0, 100.0)
        elements = [
            self._element(
                "IfcSpaceHeater",
                at,
                self.f.createIfcExtrudedAreaSolid(
                    box, self._axes((0.0, 0.0, 0.0)), self.f.createIfcDirection((0, 0, 1)), 600.0
                ),
            )
            for at in points
        ]
        kind = self._new("IfcSpaceHeaterType", Name=type_name)
        self._new("IfcRelDefinesByType", RelatedObjects=elements, RelatingType=kind)

    def columns(self, type_name: str, points: list[tuple[float, float]]) -> None:
        square = self.f.createIfcRectangleProfileDef("AREA", None, None, 300.0, 300.0)
        solid = self.f.createIfcExtrudedAreaSolid(
            square, self._axes((0.0, 0.0, 0.0)), self.f.createIfcDirection((0, 0, 1)), 3000.0
        )
        elements = [self._element("IfcColumn", at, solid) for at in points]
        kind = self._new("IfcColumnType", Name=type_name, PredefinedType="COLUMN")
        self._new("IfcRelDefinesByType", RelatedObjects=elements, RelatingType=kind)

    def pipes(self, system: str, runs: list[tuple[float, float, str, float]]) -> list[Any]:
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
            pipe = self._element("IfcPipeSegment", (x, y), solid)
            sizes = self.f.createIfcPropertySingleValue(
                "Size", None, self.f.createIfcLabel("20 mmø")
            )
            kind = self.f.createIfcPropertySingleValue(
                "System Type", None, self.f.createIfcLabel("Hydronic Supply")
            )
            self._new(
                "IfcRelDefinesByProperties",
                RelatedObjects=[pipe],
                RelatingPropertyDefinition=self._new(
                    "IfcPropertySet", Name="Mechanical", HasProperties=[sizes, kind]
                ),
            )
            elements.append(pipe)
        self.assign(elements, system)
        return elements

    def assign(self, elements: list[Any], system: str) -> None:
        group = self._new("IfcDistributionSystem", Name=system)
        self._new("IfcRelAssignsToGroup", RelatedObjects=elements, RelatingGroup=group)

    def save(self, path: Path) -> Path:
        self._new(
            "IfcRelContainedInSpatialStructure",
            RelatingStructure=self.storey,
            RelatedElements=self.contained,
        )
        self.f.write(str(path))
        return path


@pytest.fixture(scope="module")
def model(tmp_path_factory: pytest.TempPathFactory) -> Path:
    built = _Builder()
    for type_name, points in HEATERS.items():
        built.heaters(type_name, points)
    for system, runs in PIPES.items():
        built.pipes(system, runs)
    built.columns("Column 300", [(0.0, 0.0), (10.0, 0.0)])
    return built.save(tmp_path_factory.mktemp("ifc") / "heating.ifc")


def _render(model: Path, out: Path, plan: str = "heating", **options: Any) -> dict[str, Any]:
    pictures = render_model(model, out, dpi=150, **options)
    names = [p.stem for p in pictures]
    assert names == ["heating--Level_1--heating", "heating--Level_1--structural"]
    picture = pictures[names.index(f"heating--Level_1--{plan}")]
    return json.loads(picture.with_suffix(".json").read_text(encoding="utf-8"))


def test_heaters_are_drawn_where_the_model_puts_them(model: Path, tmp_path: Path) -> None:
    truth = _render(model, tmp_path)
    image = Image.open(tmp_path / truth["picture"]).convert("L")
    heaters = [s for s in truth["symbols"] if s["kind"] == "space_heater"]
    assert len(heaters) == 4
    k, (x0, y0) = truth["px_per_m"], truth["origin_m"]
    expected = sorted(
        ((x - x0) * k, (y0 - y) * k) for points in HEATERS.values() for x, y in points
    )
    found = sorted((s["x"], s["y"]) for s in heaters)
    for (ex, ey), (fx, fy) in zip(expected, found, strict=True):
        assert abs(ex - fx) <= 1 and abs(ey - fy) <= 1
        around = image.crop((round(fx) - 14, round(fy) - 14, round(fx) + 15, round(fy) + 15))
        assert min(around.tobytes()) < 128  # a symbol is drawn there
    assert truth["counts"] == {"Radiator A": 3, "Radiator B": 1}


def test_run_lengths_are_the_fact_sheets(model: Path, tmp_path: Path) -> None:
    truth = _render(model, tmp_path)
    facts = {
        f.system: f.value
        for f in mep_facts(ifcopenshell.open(str(model)))
        if f.topic == "pipe_segment.length" and f.system and f.subject == "all"
    }
    assert facts == {"Heating Supply": 9.5, "Heating Return": 4.25}
    assert truth["system_lengths_m"] == facts
    assert {(r["system"], r["size"], r["length_m"]) for r in truth["runs"]} == {
        ("Heating Supply", "20 mmø", 9.5),
        ("Heating Return", "20 mmø", 4.25),
    }
    assert {r["system"]: r["plan_m"] for r in truth["runs"]} == pytest.approx(
        {"Heating Supply": 9.5, "Heating Return": 4.25}, abs=0.05
    )


def test_legend_has_one_entry_per_type_name(model: Path, tmp_path: Path) -> None:
    assert [e["label"] for e in _render(model, tmp_path)["legend"]] == ["Radiator A", "Radiator B"]
    assert _render(model, tmp_path / "bare", variant="no-legend")["legend"] == []


def test_the_same_seed_gives_the_same_bytes(model: Path, tmp_path: Path) -> None:
    one = _render(model, tmp_path / "a", variant="scan", seed=7)
    two = _render(model, tmp_path / "b", variant="scan", seed=7)
    other = _render(model, tmp_path / "c", variant="scan", seed=8)
    a, b, c = (tmp_path / d / one["picture"] for d in "abc")
    assert one == two and a.read_bytes() == b.read_bytes()
    assert a.read_bytes() != c.read_bytes() and other["symbols"] != one["symbols"]


@pytest.mark.parametrize("variant", ["scan", "scan-colour", "photo"])
def test_a_degraded_picture_moves_its_points_with_it(
    model: Path, tmp_path: Path, variant: str
) -> None:
    clean = _render(model, tmp_path / "clean")
    truth = _render(model, tmp_path, variant=variant, seed=3)
    image = Image.open(tmp_path / truth["picture"]).convert("L")
    assert truth["symbols"] != clean["symbols"]
    for spot in truth["symbols"]:
        x, y = round(spot["x"]), round(spot["y"])
        assert min(image.crop((x - 14, y - 14, x + 15, y + 15)).tobytes()) < 128


def test_a_structural_plan_counts_columns(model: Path, tmp_path: Path) -> None:
    truth = _render(model, tmp_path, plan="structural")
    assert truth["counts"] == {"Column 300": 2}
    assert [e["label"] for e in truth["legend"]] == ["Column 300"]
    assert truth["runs"] == []


def _plumbing(path: Path, systems: dict[str, list[tuple[float, float, str, float]]]) -> Path:
    built = _Builder()
    for system, runs in systems.items():
        built.pipes(system, runs)
    return built.save(path)


def _one(model: Path, out: Path, **options: Any) -> dict[str, Any]:
    (picture,) = render_model(model, out, dpi=150, **options)
    return json.loads(picture.with_suffix(".json").read_text(encoding="utf-8"))


def test_runs_are_styled_and_counted_per_system_type(tmp_path: Path) -> None:
    built = _Builder()
    built.pipes("Waste 1", [(0.0, 0.0, "x", 3.0)])
    built.pipes("Waste 2", [(0.0, 1.0, "x", 2.0)])
    built.pipes("Vent 1", [(0.0, 2.0, "x", 4.0)])
    shared = built.pipes("Vent 7", [(0.0, 3.0, "x", 1.0)])
    built.assign(shared, "Waste 3")  # one pipe in two systems is drawn, and counted, once
    truth = _one(built.save(tmp_path / "waste.ifc"), tmp_path)
    assert [line["system"] for line in truth["legend_lines"]] == ["Vent", "Waste"]
    lengths = truth["system_lengths_m"]
    assert set(lengths) == {"Vent", "Waste"}
    assert sum(lengths.values()) == pytest.approx(10.0)
    assert lengths["Vent"] in (pytest.approx(4.0), pytest.approx(5.0))
    assert sum(r["length_m"] for r in truth["runs"]) == pytest.approx(10.0)
    assert truth["system_plan_m"] == pytest.approx(lengths, abs=0.05)
    assert truth["styles_capped"] == 0


def test_types_past_the_styles_share_a_grey_other(tmp_path: Path) -> None:
    systems = {f"T{i:02d} 1": [(0.0, float(i), "x", 2.0)] for i in range(30)}
    truth = _one(_plumbing(tmp_path / "many.ifc", systems), tmp_path)
    rows = [line["system"] for line in truth["legend_lines"]]
    assert rows == [f"T{i:02d}" for i in range(23)] + ["other systems"]
    assert truth["styles_capped"] == 7
    assert truth["system_lengths_m"]["other systems"] == pytest.approx(14.0)


@pytest.mark.parametrize("variant", ["clean", "scan", "scan-colour", "photo"])
def test_legend_boxes_hold_their_row_after_distortion(
    model: Path, tmp_path: Path, variant: str
) -> None:
    clean = _render(model, tmp_path / "clean")
    truth = _render(model, tmp_path, variant=variant, seed=3)
    image = Image.open(tmp_path / truth["picture"]).convert("L")
    flat = Image.open(tmp_path / "clean" / clean["picture"]).convert("L")
    rows = [*truth["legend"], *truth["legend_lines"]]
    assert len(rows) == 4  # two symbol rows, two line rows
    for row, before in zip(rows, [*clean["legend"], *clean["legend_lines"]], strict=True):
        x0, y0, x1, y1 = (round(v) for v in row["box"])
        assert x1 - x0 > 50 and 10 < y1 - y0 < 60
        if variant != "clean":
            assert row["box"] != before["box"]
        # the row's ink sits where it sat in the clean box: a box off by a few pixels shifts it
        here, there = _ink(image, row["box"]), _ink(flat, before["box"])
        width = row["box"][2] - row["box"][0]  # blur thickens ink, a warp widens the box
        assert here[0] > 50 and abs(here[2] - there[2]) < 2.5, (here, there)
        assert abs(here[1] - there[1]) < 0.1 * width, (here, there)  # rows differ in y


def _ink(image: Image.Image, box: list[float]) -> tuple[int, float, float]:
    """Dark pixels in the box, and their centre in pixels from the box's centre."""
    x0, y0, x1, y1 = (round(v) for v in box)
    dark = np.asarray(image.crop((x0, y0, x1, y1))) < 200  # blur greys thin ink
    ys, xs = np.nonzero(dark)
    h, w = dark.shape
    return len(xs), float(xs.mean() - w / 2), float(ys.mean() - h / 2)


def test_a_colour_scan_keeps_its_colours(model: Path, tmp_path: Path) -> None:
    truth = _render(model, tmp_path, variant="scan-colour", seed=3)
    pixels = np.asarray(Image.open(tmp_path / truth["picture"]).convert("RGB"), dtype=int)
    assert (pixels.max(axis=2) - pixels.min(axis=2)).max() > 80  # coloured lines survive
    grey = _render(model, tmp_path / "grey", variant="scan", seed=3)
    assert Image.open(tmp_path / "grey" / grey["picture"]).mode == "L"


def test_scan_noise_is_configurable(model: Path, tmp_path: Path) -> None:
    default = _render(model, tmp_path / "a", variant="scan", seed=3)
    _render(model, tmp_path / "b", variant="scan", seed=3, noise=(1.0, 0.002, 60))
    harsh = _render(model, tmp_path / "c", variant="scan", seed=3, noise=(1.5, 0.005, 40))
    rougher = _render(model, tmp_path / "d", variant="scan", seed=3, noise=(1.0, 0.002, 40))
    a, b, c, d = (tmp_path / d / default["picture"] for d in "abcd")
    assert a.read_bytes() == b.read_bytes()  # the defaults are bar 1's scan
    assert d.stat().st_size < a.stat().st_size and rougher["noise"]["quality"] == 40
    assert harsh["noise"] == {"blur": 1.5, "salt": 0.005, "quality": 40}
    assert default["noise"] == {"blur": 1.0, "salt": 0.002, "quality": 60}
    assert harsh["symbols"] == default["symbols"]  # same rotation: the seed, not the noise
    salty = _render(model, tmp_path / "e", variant="scan", seed=3, noise=(1.0, 0.02, 60))
    assert _salt(Image.open(tmp_path / "e" / salty["picture"])) > 3 * _salt(Image.open(a))
    assert c.read_bytes() != a.read_bytes()


def _salt(image: Image.Image) -> int:
    """Lone black dots on white: pixels far darker than all four neighbours."""
    full = np.asarray(image.convert("L"), dtype=int)
    centre = full[1:-1, 1:-1]
    around = np.minimum.reduce([full[:-2, 1:-1], full[2:, 1:-1], full[1:-1, :-2], full[1:-1, 2:]])
    return int((around - centre > 120).sum())
