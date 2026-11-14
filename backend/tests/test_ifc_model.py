"""The model route's adapter (`EXTRACTOR_BIM=ifc`, `SECOND_COUNTER=ifc`) on a synthetic building
model, its sheet PDF and the sheet's SVG twin: what the model lists, what the sheet draws of it,
and what the drawing carries of both."""

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.geom
import pytest
from ifc_models import IfcFile, Schema, Shape, box, sheet_svg
from jsonschema import Draft202012Validator
from pdf_sheets import WHITE, SheetPdf, rect

from app.adapters.extraction_v1 import ExtractionV1Writer
from app.adapters.ifc_model import LOOKS_FOR, IfcModelExtractor, IfcModels, IfcSecondCounter
from app.adapters.ifc_model.objects import read_model
from app.adapters.ifc_model.svg import read_svg
from app.adapters.vector_pdf.ifc_render import room_type
from app.composition import build_pipeline
from app.core.drawing.model import MeasuredValue, ModelObject, Page, Subject
from app.core.errors import InvalidInputError, NotFoundError
from app.core.pipeline.ingest import NO_SHEET
from app.core.pipeline.model import DrawingFile, Extracted, FileKind, Measurement, Sheet
from app.settings import Settings

SHEET = "data/demo/house_plan-01-level-1.pdf"
TWIN = "data/demo/house_plan-01-level-1.svg"
MODEL = "data/demo/house.ifc"
M_PER_PT = 0.0254 / 72
# The sheet is 600 x 400 pt at 1:200 and its twin 300 x 200 SVG units: metres per SVG unit.
M_PER_SVG_UNIT = 2 * 200 * M_PER_PT
PAGE = Page(page=1, width=600, height=400, unit="pt")


@dataclass(frozen=True)
class Demo:
    ifc: bytes
    svg: bytes
    pdf: bytes
    ids: dict[str, str]  # GlobalIds by the names used below


def sheet_pdf(storey: str) -> bytes:
    sheet = SheetPdf(600, 400)
    sheet.path(rect(0, 0, 600, 400), stroke=None, fill=WHITE)
    sheet.text(f"Demo house — Floor plan: {storey}", 20, 360)
    sheet.text("Scale 1:200 · cut at 1.20 m above storey level", 20, 372)
    return sheet.pdf()


def demo(titled: str = "Level 1") -> Demo:
    """A house of two storeys and the sheet of Level 1. The sheet draws two of Level 1's three
    walls (one as its two layers), its door, column and stair (as two flights), a wall of
    Level 2, a chair, and three rooms: the kitchen, the corridor around a hole, and a void of
    Level 2 that lies inside the kitchen's outline. It does not draw wall W3, the window, the
    slab, the beam or the store room."""
    model = IfcFile()
    one, two = model.storey("Level 1"), model.storey("Level 2")
    model.storey("Foundation")
    w1 = {"Length": 14.0, "NetSideArea": 35.0, "NetVolume": 7.0}
    w3 = {"Length": 3.0, "NetSideArea": 7.5, "NetVolume": 1.5}
    ids = {
        "w1": model.element("IfcWallStandardCase", storey=one, name="W1", quantities=w1),
        "w2": model.element("IfcWall", storey=one, name="W2", quantities={"Length": 7.0}),
        "w3": model.element("IfcWall", storey=one, name="W3", quantities=w3),
        "w4": model.element("IfcWall", storey=two, name="W4"),
        "door": model.element("IfcDoor", storey=one),
        "window": model.element("IfcWindow", storey=one),
        "column": model.element("IfcColumn", storey=one),
        "slab": model.element("IfcSlab", storey=one, quantities={"NetVolume": 24.0}),
        "stair": model.element("IfcStair", storey=one),
        "beam": model.element("IfcBeam"),
        "chair": model.element("IfcFurnishingElement", storey=one),
    }
    ids["layer1"] = model.element("IfcBuildingElementPart", part_of=ids["w2"])
    ids["layer2"] = model.element("IfcBuildingElementPart", part_of=ids["w2"])
    ids["flight"] = model.element("IfcStairFlight", part_of=ids["stair"])
    ids["inner_stair"] = model.element("IfcStair", part_of=ids["stair"])
    ids["inner_flight"] = model.element("IfcStairFlight", part_of=ids["inner_stair"])
    ids["kitchen"] = model.space(one, "1.2", "Kitchen", (box(0, 0, 5, 4), 0.0, 2.5))
    ids["corridor"] = model.space(one, "1.1", "Corridor", (box(5, 0, 10, 4), 0.0, 2.5))
    ids["store"] = model.space(one, "1.3", "Store", (box(0, 4, 2, 6), 0.0, 2.5))
    ids["void"] = model.space(two, "2.1", "Void", (box(2, 1, 4, 3), 3.0, 2.5))
    shapes = [
        Shape("IfcWallStandardCase", ids["w1"], [box(48, 21, 252, 25)], cut=True),
        Shape("IfcBuildingElementPart", ids["layer1"], [box(146, 25, 148, 75)], cut=True),
        Shape("IfcBuildingElementPart", ids["layer2"], [box(148, 25, 150, 75)], cut=True),
        Shape("IfcWall", ids["w4"], [box(40, 150, 120, 154)]),
        Shape("IfcDoor", ids["door"], [box(100, 75, 110, 77), box(100, 77, 102, 87)]),
        Shape("IfcColumn", ids["column"], circles=[(200, 50, 4)], cut=True),
        Shape("IfcStairFlight", ids["flight"], [box(260, 30, 280, 50)]),
        Shape("IfcStairFlight", ids["inner_flight"], [box(260, 50, 280, 70)]),
        Shape("IfcFurnishingElement", ids["chair"], [box(60, 60, 64, 64)]),
        Shape("IfcSpace", ids["kitchen"], [box(50, 25, 146, 75)], name="1.2"),
        Shape(
            "IfcSpace",
            ids["corridor"],
            [box(150, 25, 250, 75), box(190, 40, 210, 60)],
            name="1.1",
        ),
        Shape("IfcSpace", ids["void"], [box(100, 30, 140, 60)], name="2.1"),
    ]
    texts = [
        (60, 50, "1.2"),
        (60, 40, "Kitchen"),
        (160, 35, "Corridor"),
        (160, 45, "1.1"),
        (110, 45, "Void"),  # inside the kitchen's outline too
        (200, 50, "in the hole"),  # the corridor is not filled here
        (20, 180, "Demo house"),
    ]
    return Demo(model.ifc(), sheet_svg(300, 200, shapes, texts), sheet_pdf(titled), ids)


DEMO = demo()
IDS = DEMO.ids


class Files:
    def __init__(self, content: dict[str, bytes]) -> None:
        self.content = content
        self.reads: list[str] = []

    def read(self, path: str) -> bytes:
        self.reads.append(path)
        if path not in self.content:
            raise NotFoundError(f"{path} is not there")
        return self.content[path]


def stored(found: Demo) -> Files:
    return Files({SHEET: found.pdf, TWIN: found.svg, MODEL: found.ifc})


def file(path: str, kind: FileKind, data: bytes) -> DrawingFile:
    return DrawingFile(
        path=path, size=len(data), sha256=hashlib.sha256(data).hexdigest(), kind=kind
    )


def model_file(found: Demo = DEMO) -> DrawingFile:
    return file(MODEL, "ifc", found.ifc)


def sheet_of(found: Demo = DEMO) -> Sheet:
    return Sheet(file=file(SHEET, "pdf", found.pdf), pages=(PAGE,))


def extract(found: Demo = DEMO) -> Extracted:
    files = stored(found)
    return IfcModelExtractor(files, IfcModels(files)).extract(model_file(found), sheet_of(found))


def on_page(x0: float, y0: float, x1: float, y1: float) -> object:
    """A box given in SVG units, as page fractions."""
    return pytest.approx((x0 / 300, y0 / 200, x1 / 300, y1 / 200), abs=1e-5)


# The model: objects.py


def test_the_model_lists_each_class_with_its_subtypes_and_keeps_the_files_own_name() -> None:
    model = read_model(DEMO.ifc)
    assert {class_: len(found) for class_, found in model.elements.items()} == {
        "door": 1,
        "window": 1,
        "wall": 4,
        "column": 1,
        "beam": 1,
        "slab": 1,
        "railing": 0,
        "stair": 1,  # the stair inside the stair is a part of it, not a stair of its own
    }
    walls = {wall.name: wall for wall in model.elements["wall"]}
    assert (walls["W1"].source_class, walls["W2"].source_class) == (
        "IfcWallStandardCase",
        "IfcWall",
    )
    assert walls["W1"].guid == IDS["w1"]
    assert model.storeys == ("Level 1", "Level 2", "Foundation")
    assert [space.long_name for space in model.spaces] == ["Kitchen", "Corridor", "Store", "Void"]
    assert [space.name for space in model.spaces] == ["1.2", "1.1", "1.3", "2.1"]


def test_an_objects_storey_is_the_one_that_contains_it_or_what_it_is_a_part_of() -> None:
    built = IfcFile()
    one, two = built.storey("EG"), built.storey("OG")
    frame = built.element("IfcElementAssembly", storey=two)
    built.element("IfcDoor", storey=one, name="contained")
    built.element("IfcDoor", part_of=frame, name="part of an assembly")
    built.element("IfcDoor", name="nowhere")
    built.space(two, "7", "Room")
    model = read_model(built.ifc())
    assert {door.name: door.storey for door in model.elements["door"]} == {
        "contained": "EG",
        "part of an assembly": "OG",
        "nowhere": None,
    }
    assert model.spaces[0].storey == "OG"  # a space is a part of its storey
    assert [door.name for door in model.on_storey("door", "EG")] == ["contained"]
    assert [door.name for door in model.on_storey("door", None)] == ["nowhere"]


def test_an_objects_parts_are_everything_below_it_at_any_depth() -> None:
    model = read_model(DEMO.ifc)
    (stair,) = model.elements["stair"]
    assert stair.guid == IDS["stair"]
    assert set(stair.parts) == {IDS["flight"], IDS["inner_stair"], IDS["inner_flight"]}
    walls = {wall.name: wall for wall in model.elements["wall"]}
    assert set(walls["W2"].parts) == {IDS["layer1"], IDS["layer2"]}
    assert walls["W1"].parts == ()


def test_walls_and_slabs_carry_the_quantities_the_file_states_and_no_others() -> None:
    model = read_model(DEMO.ifc)
    walls = {wall.name: wall.quantities for wall in model.elements["wall"]}
    assert walls == {
        "W1": {"length_m": 14.0, "side_area_m2": 35.0, "volume_m3": 7.0},
        "W2": {"length_m": 7.0},  # the file states no area and no volume for it
        "W3": {"length_m": 3.0, "side_area_m2": 7.5, "volume_m3": 1.5},
        "W4": {},
    }
    assert model.elements["slab"][0].quantities == {"volume_m3": 24.0}
    assert model.elements["door"][0].quantities == {}


@pytest.mark.parametrize("schema", ["IFC4", "IFC2X3"])
@pytest.mark.parametrize(
    ("millimetres", "area_units", "stated"),
    [
        (False, True, {"Length": 5.0, "NetSideArea": 12.5, "NetVolume": 2.5}),
        (True, True, {"Length": 5000.0, "NetSideArea": 12.5, "NetVolume": 2.5}),
        # no area or volume unit named: they are in the length unit, squared and cubed
        (True, False, {"Length": 5000.0, "NetSideArea": 12.5e6, "NetVolume": 2.5e9}),
    ],
    ids=["metres", "millimetres", "millimetres-only"],
)
def test_quantities_and_areas_are_in_metres_whatever_the_files_unit(
    schema: Schema, millimetres: bool, area_units: bool, stated: dict[str, float]
) -> None:
    built = IfcFile(schema=schema, millimetres=millimetres, area_units=area_units)
    storey = built.storey("EG")
    built.element("IfcWallStandardCase", storey=storey, quantities=stated)
    built.space(storey, "1", "Room", (box(0, 0, 5, 4), 0.0, 2.5))
    model = read_model(built.ifc())
    assert model.elements["wall"][0].quantities == pytest.approx(
        {"length_m": 5.0, "side_area_m2": 12.5, "volume_m3": 2.5}
    )
    assert model.spaces[0].quantities == pytest.approx({"area_m2": 20.0})


def test_a_spaces_area_is_the_floor_its_solid_covers_each_spot_once() -> None:
    built = IfcFile()
    storey = built.storey("EG")
    corner = [(0.0, 0.0), (4.0, 0.0), (4.0, 2.0), (2.0, 2.0), (2.0, 4.0), (0.0, 4.0)]
    built.space(storey, "1", "L-shaped", (corner, 0.0, 2.5))
    # under a stair: the floor steps up, and the two solids overlap by 2 x 3 m on plan
    built.space(storey, "2", "Stepped", (box(0, 0, 4, 3), 0.0, 2.5), (box(2, 0, 6, 3), 1.0, 1.5))
    built.space(storey, "3", "No solid")
    areas = {space.long_name: space.quantities for space in read_model(built.ifc()).spaces}
    assert areas == {
        "L-shaped": pytest.approx({"area_m2": 12.0}),
        "Stepped": pytest.approx({"area_m2": 18.0}),  # not 12 + 12
        "No solid": {},
    }


@pytest.mark.parametrize("data", [b"not a model", b"ISO-10303-21;\nHEADER;"], ids=["text", "cut"])
def test_a_file_that_is_no_ifc_model_is_refused(data: bytes) -> None:
    with pytest.raises(InvalidInputError, match="not an IFC file"):
        read_model(data)


def test_a_model_without_a_project_has_no_units_and_is_refused() -> None:
    with pytest.raises(InvalidInputError, match="no IfcProject"):
        read_model(ifcopenshell.file(schema="IFC4").to_string().encode())


# The twin: svg.py


def test_the_twin_gives_one_shape_per_object_by_its_global_id() -> None:
    svg = read_svg(
        sheet_svg(
            300,
            200,
            [
                Shape("IfcWall", "wall-guid", [box(0, 0, 10, 2), box(20, 0, 30, 2)], cut=True),
                Shape("IfcSpace", "space-guid", [box(0, 10, 10, 20)], name="1.2"),
                Shape("IfcColumn", "round-guid", circles=[(100, 50, 4)]),
                Shape("IfcDoor", "arc-guid", d="M0,0 L10,0 A5 5 0 0 1 20,10 L0,10 Z"),
                Shape("IfcDoor", None, [box(0, 0, 1, 1)]),  # no GlobalId: nobody's shape
                Shape("annotation", "note-guid", [box(0, 0, 1, 1)]),  # not an IFC class
                Shape("IfcWindow", "empty-guid"),  # nothing drawn
            ],
            [(5, 15, " Kitchen "), (5, 18, "  ")],
        )
    )
    assert list(svg.groups) == ["wall-guid", "space-guid", "round-guid", "arc-guid"]
    wall = svg.groups["wall-guid"]
    assert (wall.ifc_class, wall.name) == ("IfcWall", None)  # "cut" is a style, not the class
    assert wall.rings == (
        ((0, 0), (10, 0), (10, 2), (0, 2)),
        ((20, 0), (30, 0), (30, 2), (20, 2)),
    )
    assert len(wall.points) == 8
    assert svg.groups["space-guid"].name == "1.2"
    # an arc counts by the point it ends at
    assert svg.groups["arc-guid"].rings == (((0, 0), (10, 0), (20, 10), (0, 10)),)
    (circle,) = svg.groups["round-guid"].rings
    assert len(circle) == 16
    assert all(math.hypot(x - 100, y - 50) == pytest.approx(4) for x, y in circle)
    assert [(text.at, text.text) for text in svg.texts] == [((5, 15), "Kitchen")]


def test_a_point_of_the_twin_is_a_fraction_of_the_sheet_from_the_view_boxs_corner() -> None:
    svg = read_svg(b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="10 20 300 200"/>')
    assert svg.view_box == (10, 20, 300, 200)
    assert svg.fraction((160, 70)) == pytest.approx((0.5, 0.25))


@pytest.mark.parametrize(
    "data",
    [
        b"<svg",
        b'<svg xmlns="http://www.w3.org/2000/svg"/>',
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300"/>',
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 0 200"/>',
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 wide high"/>',
    ],
    ids=["not-xml", "no-view-box", "three-numbers", "no-width", "not-numbers"],
)
def test_a_twin_without_a_usable_view_box_is_refused(data: bytes) -> None:
    with pytest.raises(InvalidInputError, match="SVG"):
        read_svg(data)


# The sheet: sheet.py, through the extractor


def test_what_the_sheet_draws_becomes_elements_named_by_the_model() -> None:
    found = extract()
    by_name = {
        name: element
        for name, guid in IDS.items()
        for element in found.elements
        if element.attrs["global_id"] == guid
    }
    assert {name: element.class_ for name, element in by_name.items()} == {
        "w1": "wall",
        "w2": "wall",
        "w4": "wall",
        "door": "door",
        "column": "column",
        "stair": "stair",
    }
    assert len(found.elements) == 6  # the chair has no class here, W3 and the slab no shape
    assert sorted(element.id for element in found.elements) == [f"e{n}" for n in range(1, 7)]
    assert all((element.page, element.plan) == (1, "p1") for element in found.elements)
    w1 = by_name["w1"]
    assert w1.box == on_page(48, 21, 252, 25)
    assert w1.attrs == {
        "source_class": "IfcWallStandardCase",
        "global_id": IDS["w1"],
        "storey": "Level 1",
        "parts": 1,
        "length_m": 14.0,
        "net_side_area_m2": 35.0,
        "net_volume_m3": 7.0,
    }
    assert w1.polygon is not None and len(w1.polygon) == 4  # drawn as one ring: its outline
    assert by_name["w4"].attrs["storey"] == "Level 2"  # another storey's wall, drawn here
    assert by_name["column"].box == on_page(196, 46, 204, 54)
    assert by_name["door"].box == on_page(100, 75, 110, 87)


def test_an_object_drawn_as_its_parts_is_one_element_around_them() -> None:
    found = extract()
    by_guid = {element.attrs["global_id"]: element for element in found.elements}
    w2, stair = by_guid[IDS["w2"]], by_guid[IDS["stair"]]
    assert w2.box == on_page(146, 25, 150, 75)  # its two layers
    assert (w2.attrs["parts"], w2.polygon) == (2, None)
    # What the file states for it, though wall W3 of the same storey is not drawn: the
    # storey's sums are over the model's list, not over these elements.
    assert (w2.attrs["length_m"], "net_volume_m3" in w2.attrs) == (7.0, False)
    assert stair.box == on_page(260, 30, 280, 70)  # its flight and the inner stair's flight
    assert stair.attrs["parts"] == 2


def test_rooms_are_the_drawn_spaces_with_outline_area_label_and_storey() -> None:
    found = extract()
    kitchen, corridor, void = found.rooms
    assert (kitchen.id, kitchen.label, kitchen.type) == ("r1", "Kitchen 1.2", "kitchen")
    assert kitchen.box == on_page(50, 25, 146, 75)
    assert kitchen.polygon is not None and len(kitchen.polygon) == 4
    assert kitchen.area_m2 == pytest.approx(96 * 50 * M_PER_SVG_UNIT**2, abs=0.002)
    assert kitchen.attrs == {
        "number": "1.2",
        "storey": "Level 1",
        "global_id": IDS["kitchen"],
        "foreign": False,
        "source_class": "IfcSpace",
        "ifc_name": "1.2",
        "ifc_long_name": "Kitchen",
    }
    # the inner ring is a hole (even-odd), and the text in the hole is not the corridor's
    assert (corridor.label, corridor.type) == ("Corridor 1.1", "hall")
    assert corridor.area_m2 == pytest.approx((100 * 50 - 20 * 20) * M_PER_SVG_UNIT**2, abs=0.002)
    # a text inside two rooms belongs to the smaller one; a space of another storey is foreign
    assert (void.id, void.label) == ("r3", "Void")
    assert (void.attrs["foreign"], void.attrs["storey"]) == (True, "Level 2")


def test_the_plan_is_around_everything_listed_and_the_scale_is_the_sheets() -> None:
    found = extract()
    (plan,) = found.plans
    assert (plan.id, plan.page, plan.storey) == ("p1", 1, "Level 1")
    assert plan.box == on_page(40, 21, 280, 154)
    assert (found.scale.status, found.scale.text) == ("scaled", "1:200")
    assert found.scale.m_per_unit == pytest.approx(200 * M_PER_PT, rel=1e-5)
    assert (found.method, found.read) == ("plan_drawing", LOOKS_FOR)
    assert found.read == (
        "room", "door", "window", "wall", "column", "beam", "slab", "railing", "stair"
    )  # fmt: skip


@pytest.mark.parametrize(
    ("titled", "storey", "kitchen_is_foreign"),
    [
        ("Level 1", "Level 1", False),
        ("Level 2", "Level 2", True),  # the title names a storey with objects: it is believed
        ("Foundation", "Level 1", False),  # a storey with nothing on it: the most drawn one
        ("Attic", "Level 1", False),  # not a storey of the model
    ],
)
def test_the_sheets_storey_is_the_titled_one_when_the_model_has_objects_on_it(
    titled: str, storey: str, kitchen_is_foreign: bool
) -> None:
    found = extract(demo(titled))
    assert found.plans[0].storey == storey
    assert found.rooms[0].attrs["foreign"] is kitchen_is_foreign


def test_the_notes_count_what_the_storey_has_undrawn_and_shapes_without_a_class() -> None:
    assert extract().notes[-2:] == (
        "the model lists on storey Level 1, and this sheet does not draw: "
        "1 slab, 1 wall, 1 window",  # the beam has no storey
        "drawn shapes of classes the drawing model has no name for: 1 IfcFurnishingElement",
    )


# model_objects


def test_the_drawing_lists_every_object_of_the_model_drawn_or_not() -> None:
    found = extract()
    assert found.model_objects is not None
    listed = {item.global_id: item for item in found.model_objects}
    assert [item.class_ for item in found.model_objects] == [
        "door", "window", "wall", "wall", "wall", "wall", "column", "beam", "slab", "stair",
        "space", "space", "space", "space",
    ]  # fmt: skip
    # No part, no inner stair, no chair. Ids are the list's own.
    assert [item.id for item in found.model_objects] == [f"m{n}" for n in range(1, 15)]
    drawn = {element.attrs["global_id"]: element.id for element in found.elements}
    assert listed[IDS["w1"]] == ModelObject(
        id=listed[IDS["w1"]].id,
        class_="wall",
        storey="Level 1",
        global_id=IDS["w1"],
        name="W1",
        long_name=None,
        quantities={"length_m": 14.0, "side_area_m2": 35.0, "volume_m3": 7.0},
        element=drawn[IDS["w1"]],
        attrs={"source_class": "IfcWallStandardCase"},
    )
    w3 = listed[IDS["w3"]]  # not drawn: no element, and everything the model says of it
    assert (w3.element, w3.storey, w3.quantities) == (
        None,
        "Level 1",
        {"length_m": 3.0, "side_area_m2": 7.5, "volume_m3": 1.5},
    )
    assert (listed[IDS["slab"]].element, listed[IDS["slab"]].quantities) == (
        None,
        {"volume_m3": 24.0},
    )
    assert (listed[IDS["w4"]].storey, listed[IDS["w4"]].element) == ("Level 2", drawn[IDS["w4"]])
    assert (listed[IDS["beam"]].storey, listed[IDS["beam"]].element) == (None, None)
    assert listed[IDS["w2"]].element == drawn[IDS["w2"]]  # drawn as its parts


def test_a_listed_space_has_its_solids_footprint_and_the_room_it_is_drawn_as() -> None:
    found = extract()
    assert found.model_objects is not None
    spaces = {item.long_name: item for item in found.model_objects if item.class_ == "space"}
    kitchen = spaces["Kitchen"]
    assert (kitchen.name, kitchen.storey, kitchen.element) == ("1.2", "Level 1", "r1")
    # 5 x 4 m in the model, whatever the sheet's outline measures (rooms[0].area_m2)
    assert kitchen.quantities == pytest.approx({"area_m2": 20.0})
    assert kitchen.attrs == {"source_class": "IfcSpace"}
    assert (spaces["Store"].element, spaces["Store"].quantities) == (
        None,
        pytest.approx({"area_m2": 4.0}),
    )
    assert (spaces["Void"].storey, spaces["Void"].element) == ("Level 2", "r3")
    assert spaces["Corridor"].element == "r2"


def test_every_drawn_item_is_named_by_exactly_one_listed_object() -> None:
    found = extract()
    named = [item.element for item in found.model_objects or () if item.element is not None]
    items = [*(element.id for element in found.elements), *(room.id for room in found.rooms)]
    assert sorted(named) == sorted(items)
    assert not {item.id for item in found.model_objects or ()} & set(items)


def test_a_model_asked_about_itself_gives_its_objects_and_nothing_drawn() -> None:
    files = stored(DEMO)
    extractor = IfcModelExtractor(files, IfcModels(files))
    alone = extractor.extract(model_file(), Sheet(file=model_file(), pages=()))
    assert (alone.method, alone.read) == ("ifc_model", LOOKS_FOR)
    assert (alone.plans, alone.elements, alone.rooms) == ((), (), ())
    assert (alone.scale.status, alone.scale.text) == ("scaled", "model units (IFC)")
    assert files.reads == [MODEL]  # neither the sheet nor its twin
    on_the_sheet = extract().model_objects or ()
    assert len(on_the_sheet) == 14
    assert alone.model_objects == tuple(
        item.model_copy(update={"element": None}) for item in on_the_sheet
    )


# A sheet that cannot be read through its model


def nothing_read(files: Files, source: DrawingFile, sheet: Sheet) -> str:
    found = IfcModelExtractor(files, IfcModels(files)).extract(source, sheet)
    assert (found.read, found.model_objects) == ((), None)  # nothing looked for: no count is 0
    assert (found.plans, found.elements, found.rooms) == ((), (), ())
    assert found.scale.status == "no_scale"
    (note,) = found.notes
    return note


def test_without_the_twin_nothing_is_read_and_the_note_says_why() -> None:
    files = Files({SHEET: DEMO.pdf, MODEL: DEMO.ifc})
    assert nothing_read(files, model_file(), sheet_of()) == (
        f"ifc extractor: {TWIN} is missing, so the model's objects cannot be placed on the sheet"
    )


def test_a_twin_of_another_shape_than_the_page_is_not_used() -> None:
    files = stored(DEMO)
    files.content[TWIN] = sheet_svg(300, 300, [])
    assert nothing_read(files, model_file(), sheet_of()) == (
        f"ifc extractor: {TWIN} does not have the shape of {SHEET}"
    )


def test_a_source_that_is_no_model_or_a_sheet_that_is_no_pdf_is_not_read() -> None:
    files = stored(DEMO)
    pdf_source = file(SHEET, "pdf", DEMO.pdf)
    assert nothing_read(files, pdf_source, sheet_of()) == (
        f"ifc extractor: the source {SHEET} is pdf, not an IFC model"
    )
    image = Sheet(file=file("data/demo/house_plan-01-level-1.png", "png", b"pixels"), pages=(PAGE,))
    assert nothing_read(files, model_file(), image) == (
        "ifc extractor: data/demo/house_plan-01-level-1.png is png: only a PDF sheet has an "
        "SVG twin"
    )


# The second counter


BAR = Measurement(
    quantity="scale",
    subject=Subject(kind="sheet", ref=None),
    value=MeasuredValue(value=0.07, unit="m/pt", method="scale_bar"),
)


class SheetCounter:
    """The sheet file's own second counter: one scale bar reading, wherever it looks."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def measure(self, source: DrawingFile, sheet: Sheet) -> list[Measurement]:
        self.calls.append((source.path, sheet.file.path))
        return [BAR]


def test_the_second_counter_gives_what_the_model_lists_on_the_sheets_storey() -> None:
    files, sheets = stored(DEMO), SheetCounter()
    counter = IfcSecondCounter(files, IfcModels(files), sheets)
    own, *counts, rooms = counter.measure(model_file(), sheet_of())
    assert own == BAR  # the sheet PDF's own readings are passed on
    assert sheets.calls == [(SHEET, SHEET)]
    assert {found.quantity for found in counts} == {"element_count"}
    assert {found.value.method for found in (*counts, rooms)} == {"ifc_model"}
    assert [(found.subject.kind, found.subject.ref, found.value.value) for found in counts] == [
        ("class", "door", 1),
        ("class", "window", 1),
        ("class", "wall", 3),  # W1, W2 and the undrawn W3; W4 is on Level 2
        ("class", "column", 1),
        ("class", "beam", 0),  # the one beam has no storey
        ("class", "slab", 1),
        ("class", "railing", 0),
        ("class", "stair", 1),
    ]
    assert (rooms.quantity, rooms.subject, rooms.value.value, rooms.value.unit) == (
        "room_count",
        Subject(kind="sheet", ref=None),
        3,  # kitchen, corridor and the undrawn store; the void is on Level 2
        "rooms",
    )


def test_the_second_counter_leaves_a_sheet_without_a_model_to_the_sheets_own_counter() -> None:
    files, sheets = stored(DEMO), SheetCounter()
    counter = IfcSecondCounter(files, IfcModels(files), sheets)
    cad = file("data/demo/house_plan-01-level-1.dxf", "dxf", b"0\nSECTION\n")
    assert counter.measure(cad, sheet_of()) == [BAR]
    # It is handed the group's source as it came, and no model is looked for.
    assert (sheets.calls, files.reads) == ([(cad.path, SHEET)], [])


def test_the_second_counter_adds_nothing_when_the_sheet_cannot_be_read_through_the_model() -> None:
    files = Files({SHEET: DEMO.pdf, MODEL: DEMO.ifc})  # no twin
    counter = IfcSecondCounter(files, IfcModels(files), SheetCounter())
    assert counter.measure(model_file(), sheet_of()) == [BAR]


# The model cache


def small_model(storey: str) -> bytes:
    built = IfcFile()
    built.storey(storey)
    return built.ifc()


def test_a_model_is_parsed_once_for_all_its_sheets() -> None:
    data = small_model("EG")
    files = Files({MODEL: data})
    models = IfcModels(files)
    first = models.model(file(MODEL, "ifc", data))
    assert models.model(file(MODEL, "ifc", data)) is first
    assert files.reads == [MODEL]
    assert first.storeys == ("EG",)


def test_the_oldest_model_is_dropped_when_too_many_are_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.adapters.ifc_model.MODELS_KEPT", 2)
    content = {f"data/demo/{name}.ifc": small_model(name) for name in ("a", "b", "c")}
    files = Files(content)
    models = IfcModels(files)
    a, b, c = (file(path, "ifc", data) for path, data in content.items())
    for wanted in (a, b, a, c, b, a):  # c pushes a out, the oldest; b stays
        models.model(wanted)
    assert files.reads == [a.path, b.path, c.path, a.path]


# The route end to end, through the composition root, on a dataset folder

SCHEMA = Path(__file__).parents[2] / "eval" / "schemas" / "extraction_v1.schema.json"


def ingested(root: Path, monkeypatch: pytest.MonkeyPatch, **env: str) -> tuple[Any, Path]:
    """The demo house as a dataset folder, its sheet and its model run through ingest."""
    for path, data in stored(DEMO).content.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_bytes(data)
    monkeypatch.chdir(root)  # so a developer's backend/.env can't change the result
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    out = root / "extraction"
    sink = ExtractionV1Writer(out, {SHEET: "dev", MODEL: "dev"})
    return build_pipeline(Settings(), root).ingest([SHEET, MODEL], sink), out


def test_with_the_default_settings_the_sheet_and_the_model_are_read_and_written_as_extraction_v1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report, out = ingested(tmp_path, monkeypatch)
    assert report.set_aside == ()
    assert [(sheet.file, sheet.route, sheet.source) for sheet in report.sheets] == [
        (SHEET, "bim", MODEL),
        (MODEL, "bim", MODEL),
    ]
    schema = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    of_sheet = json.loads((out / "demo" / "house_plan-01-level-1.pdf.json").read_text())
    of_model = json.loads((out / "demo" / "house.ifc.json").read_text())
    schema.validate(of_sheet)
    schema.validate(of_model)
    assert (len(of_sheet["pages"]), len(of_sheet["elements"]), len(of_sheet["rooms"])) == (1, 6, 3)
    assert len(of_sheet["model_objects"]) == len(of_model["model_objects"]) == 14
    assert (of_model["pages"], of_model["plans"], of_model["elements"]) == ([], [], [])
    assert of_model["read"] == list(LOOKS_FOR)
    # Stage 8: the sheet draws two of Level 1's walls, the model lists three.
    (walls,) = (
        entry
        for entry in of_sheet["conflicts"]
        if entry["quantity"] == "element_count" and entry["subject"]["ref"] == "wall"
    )
    assert walls["status"] == "conflict"
    assert [(value["method"], value["value"]) for value in walls["values"]] == [
        ("plan_drawing", 2.0),
        ("ifc_model", 3.0),
    ]


def test_without_the_ifc_reader_the_sheet_is_read_alone_and_the_model_is_set_aside(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report, out = ingested(tmp_path, monkeypatch, EXTRACTOR_BIM="hello")
    assert [(sheet.file, sheet.route, sheet.source) for sheet in report.sheets] == [
        (SHEET, "vector", SHEET)
    ]
    assert [(found.path, found.reason) for found in report.set_aside] == [(MODEL, NO_SHEET)]
    of_sheet = json.loads((out / "demo" / "house_plan-01-level-1.pdf.json").read_text())
    assert "model_objects" not in of_sheet
    assert not (out / "demo" / "house.ifc.json").exists()


# a space's windows (windows.py)

ROOM = (box(0, 0, 4, 3), 0.0, 2.5)  # a room's solid: 4 x 3 m, 2.5 m high, on the ground


def test_a_spaces_windows_are_the_models_by_boundary_by_shape_or_by_placement() -> None:
    model = IfcFile()
    one, two = model.storey("Level 1"), model.storey("Level 2")
    bedroom = model.space(one, "1.1", "Bedroom", ROOM)
    corridor = model.space(one, "1.2", "Corridor", (box(4, 0, 6, 3), 0.0, 2.5))
    upstairs = model.space(two, "2.1", "Bedroom", (box(0, 0, 4, 3), 3.0, 2.5))
    # in the bedroom's outer wall, 0.2 m outside its footprint
    shaped = model.window(one, "shaped", solid=(box(1, -0.3, 2, -0.2), 0.9, 1.2))
    # no shape: placed 0.1 m outside the corridor, 1.2 m high from 0.9 m up
    placed = model.window(one, "placed", at=(5.0, -0.1, 0.9), height=1.2)
    stated = model.window(one, "stated")  # no shape and no place: only the model's own word
    model.boundary(bedroom, stated)
    model.boundary(bedroom, shaped)  # said twice, by the model and by its shape: counted once
    # above the bedroom, in the same place seen from above: the storey over it
    above = model.window(two, "above", solid=(box(1, -0.3, 2, -0.2), 3.9, 1.2))
    model.window(one, "far", solid=(box(1, -1.0, 2, -0.9), 0.9, 1.2))  # 0.9 m off: nobody's

    spaces = {space.guid: space for space in read_model(model.ifc()).spaces}

    assert spaces[bedroom].windows == (shaped, stated)  # in the file's order
    assert spaces[corridor].windows == (placed,)
    assert spaces[upstairs].windows == (above,)


def test_a_space_has_no_window_only_when_every_window_of_the_model_has_a_shape() -> None:
    def windows(*, placed_too: bool, any_window: bool = True) -> tuple[str, ...] | None:
        model = IfcFile()
        one = model.storey("Level 1")
        inner = model.space(one, "1.1", "Bedroom", (box(10, 0, 14, 3), 0.0, 2.5))
        model.space(one, "1.2", "Living", ROOM)
        if any_window:
            model.window(one, "shaped", solid=(box(1, -0.3, 2, -0.2), 0.9, 1.2))
        if placed_too:
            model.window(one, "placed", at=(30.0, 0.0, 0.9), height=1.2)
        return next(s.windows for s in read_model(model.ifc()).spaces if s.guid == inner)

    assert windows(placed_too=False) == ()  # every window has a shape, none is at this room
    assert windows(placed_too=True) is None  # one is placed by a point only: it may be missed
    assert windows(placed_too=False, any_window=False) is None  # the model has no windows


def test_a_space_without_a_solid_has_the_windows_the_model_states_and_no_others() -> None:
    model = IfcFile()
    one = model.storey("Level 1")
    stated = model.space(one, "1.1", "Bedroom")
    unknown = model.space(one, "1.2", "Bedroom")
    window = model.window(one, "shaped", solid=(box(1, -0.3, 2, -0.2), 0.9, 1.2))
    model.boundary(stated, window)

    spaces = {space.guid: space for space in read_model(model.ifc()).spaces}

    assert (spaces[stated].windows, spaces[unknown].windows) == ((window,), None)


def test_a_model_in_millimetres_places_a_shapeless_window_in_metres() -> None:
    model = IfcFile(millimetres=True)
    one = model.storey("Level 1")
    bedroom = model.space(one, "1.1", "Bedroom", ROOM)
    placed = model.window(one, "placed", at=(2.0, -0.1, 0.9), height=1.2)

    (space,) = read_model(model.ifc()).spaces

    assert (space.guid, space.windows) == (bedroom, (placed,))


@pytest.mark.parametrize("millimetres", [False, True])
def test_the_copies_of_one_window_shape_are_built_once_and_each_is_where_it_is_placed(
    millimetres: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = IfcFile(millimetres=millimetres)
    one = model.storey("Level 1")
    south = model.space(one, "1.1", "Bedroom", (box(4, 0, 8, 3), 0.0, 2.5))
    east = model.space(one, "1.2", "Bedroom", (box(24, 0, 28, 3), 0.0, 2.5))
    turned = model.space(one, "1.3", "Bedroom", (box(40, 4, 44, 8), 0.0, 2.5))
    # The shape is 5 to 6 m along its own x axis: in the first room's south wall as it is, in
    # the second's moved 20 m, and in the third's west wall moved 40 m and turned a quarter.
    copies = model.window_copies(
        one,
        (box(5, -0.1, 6, 0.1), 0.9, 1.2),
        [
            ((0.0, 0.0, 0.0), (1.0, 0.0)),
            ((20.0, 0.0, 0.0), (1.0, 0.0)),
            ((40.0, 0.0, 0.0), (0.0, 1.0)),
        ],
    )
    built: list[str] = []
    create_shape = ifcopenshell.geom.create_shape

    def counted(settings: Any, inst: Any, *args: Any, **kwargs: Any) -> Any:
        built.append(inst.is_a())
        return create_shape(settings, inst, *args, **kwargs)

    monkeypatch.setattr(ifcopenshell.geom, "create_shape", counted)

    spaces = {space.guid: space.windows for space in read_model(model.ifc()).spaces}

    assert spaces == {south: (copies[0],), east: (copies[1],), turned: (copies[2],)}
    assert built.count("IfcWindow") == 1


def test_a_listed_space_says_how_many_windows_it_has_and_which() -> None:
    model = IfcFile()
    one = model.storey("Level 1")
    bedroom = model.space(one, "1.1", "Bedroom", ROOM)
    model.space(one, "1.2", "Store", (box(10, 0, 12, 3), 0.0, 2.5))
    first = model.window(one, "first", solid=(box(1, -0.3, 2, -0.2), 0.9, 1.2))
    second = model.window(one, "second", solid=(box(2.5, -0.3, 3.5, -0.2), 0.9, 1.2))
    shapes = [Shape("IfcSpace", bedroom, [box(50, 25, 146, 75)], name="1.1")]
    found = extract(Demo(model.ifc(), sheet_svg(300, 200, shapes), sheet_pdf("Level 1"), {}))

    assert found.model_objects is not None
    listed = {item.global_id: item for item in found.model_objects}
    spaces = {item.long_name: item for item in found.model_objects if item.class_ == "space"}
    # Neither window is drawn on the sheet: the room has them all the same.
    assert (listed[first].element, listed[second].element) == (None, None)
    assert spaces["Bedroom"].attrs == {
        "source_class": "IfcSpace",
        "windows": 2,
        "window_ids": f"{listed[first].id} {listed[second].id}",
    }
    assert spaces["Store"].attrs == {"source_class": "IfcSpace", "windows": 0}


# a room's type from its label in the model's language (vector_pdf/ifc_render.py ROOM_WORDS)


@pytest.mark.parametrize(
    ("label", "kind"),
    [
        ("MAGAMISTUBA 5-2", "bedroom"),  # Estonian
        ("ELUTUBA+KÖÖK 24-1", "living"),  # a living room with its kitchen, not a kitchen
        ("KÖÖK 3", "kitchen"),
        ("TUALETTRUUM 23-4", "wc"),
        ("ESIK 28-2", "hall"),
        ("KORIDOR 119", "hall"),
        ("SAUN", "sauna"),
        ("2IZQ-HAB3 01.32", "bedroom"),  # Spanish flat codes: floor, side, room
        ("2IZQ-SAL 01.39", "living"),
        ("2DER-COC 01.37", "kitchen"),
        ("2IZQ-BAÑ 01.36", "bathroom"),
        ("2IZQ-DIST 01.33", "hall"),
        ("1 RELLANO", "hall"),
        ("doucheruimte", "bathroom"),  # Dutch
        ("werkkast", "storage"),
        ("Zimmer", "bedroom"),  # German: a flat's room
        ("Vorr.", "hall"),
        ("Comunication 0.2", "hall"),  # as one model spells it
    ],
)
def test_a_room_is_typed_from_its_label_in_the_models_language(label: str, kind: str) -> None:
    assert room_type(label) == kind


@pytest.mark.parametrize(
    "label",
    ["2IZQ-DES 01.38", "Room 0.3", "Buero Meier", "PESUKODA 4", "TREPIKODA 2", "Floor", ""],
)
def test_a_label_no_word_names_stays_other(label: str) -> None:
    assert room_type(label) == "other"


@pytest.mark.parametrize(
    ("label", "kind"),
    [
        ("Wohnküche", "kitchen"),
        ("Badezimmer", "other"),  # no word of its own yet: "Zimmer" inside a word is not a room
        ("Wohnzimmer", "living"),
        ("Schlafzimmer", "bedroom"),
        ("Kitchen 1.2", "kitchen"),
        ("Corridor 1.1", "hall"),
        ("Loggia", "balcony"),
        ("Disabled toilet", "wc"),
    ],
)
def test_the_added_words_leave_typed_labels_as_they_were(label: str, kind: str) -> None:
    assert room_type(label) == kind
