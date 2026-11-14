"""The vector route's PDF extractor (`EXTRACTOR_VECTOR=pdf`) on synthetic sheets drawn in the two
styles it has reading rules for. Each test names the rule it holds in place."""

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from pdf_sheets import BLACK, WHITE, Point, SheetPdf, rect, ring

from app.adapters.extraction_v1 import ExtractionV1Writer
from app.adapters.ifc_model import IfcModels, IfcSecondCounter
from app.adapters.vector_pdf import PdfSecondCounter, PdfVectorExtractor, ifc_render, swiss
from app.adapters.vector_pdf.objects import FILL_EVEN_ODD, FILL_NONE, FILL_WINDING, read_page
from app.adapters.vector_pdf.scale import M_PER_PT_ON_PAPER, read_scale
from app.composition import build_pipeline
from app.core.drawing.model import Page
from app.core.pipeline.model import DrawingFile, Extracted, Measurement, Sheet
from app.settings import Settings

SCHEMA = Path(__file__).parents[2] / "eval" / "schemas" / "extraction_v1.schema.json"
M_PER_PT = 100 * M_PER_PT_ON_PAPER  # at 1:100
GREY, DOOR_GREY, RED = (138, 138, 138), (68, 68, 68), (176, 58, 46)
SPACE, SOLID, SPACE_EDGE = (227, 237, 247), (74, 74, 74), (138, 160, 184)


def turned(points: list[Point], degrees: float, about: Point) -> list[Point]:
    cos, sin = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return [
        (
            about[0] + (x - about[0]) * cos - (y - about[1]) * sin,
            about[1] + (x - about[0]) * sin + (y - about[1]) * cos,
        )
        for x, y in points
    ]


def area_m2(width_pt: float, height_pt: float) -> float:
    return width_pt * height_pt * M_PER_PT**2


class Files:
    def __init__(self, content: dict[str, bytes]) -> None:
        self.content = content

    def read(self, path: str) -> bytes:
        return self.content[path]


def source_and_sheet(pdf: bytes, sheet_page: Page | None) -> tuple[DrawingFile, Sheet]:
    """The PDF as the source, and the sheet to place on: the PDF itself or its render."""
    source = DrawingFile(path="data/demo/plan.pdf", size=len(pdf), sha256="0" * 64, kind="pdf")
    if sheet_page is None:
        page = read_page(pdf)
        own = Page(page=1, width=page.width, height=page.height, unit="pt")
        return source, Sheet(file=source, pages=(own,))
    other = source.model_copy(update={"path": "data/demo/plan.png", "kind": "png"})
    return source, Sheet(file=other, pages=(sheet_page,))


def extract(pdf: bytes, sheet_page: Page | None = None) -> Extracted:
    """Run the extractor on `pdf`, placing the result on the PDF itself or on another sheet."""
    source, sheet = source_and_sheet(pdf, sheet_page)
    return PdfVectorExtractor(Files({source.path: pdf})).extract(source, sheet)


def measure_again(pdf: bytes, sheet_page: Page | None = None) -> list[Measurement]:
    """Run the second counter on `pdf`, for the PDF itself or for another sheet."""
    source, sheet = source_and_sheet(pdf, sheet_page)
    return PdfSecondCounter(Files({source.path: pdf})).measure(source, sheet)


# --------------------------------------------------------------------------- the object reader


def test_paths_come_back_with_style_and_top_left_coordinates() -> None:
    sheet = SheetPdf(600, 400)
    sheet.path(rect(100, 50, 300, 150), stroke=GREY, width=0.37, fill=WHITE)
    sheet.path(rect(10, 10, 50, 30), rect(20, 15, 30, 25), stroke=None, fill=SOLID, even_odd=True)
    sheet.path([(0, 0), (10, 10)], stroke=BLACK, width=0.51)
    page = read_page(sheet.pdf())
    assert (page.width, page.height, page.page_count) == (600, 400, 1)
    room, solid, line = page.paths
    assert (room.segments, room.fill_mode, room.stroked) == (5, FILL_WINDING, True)
    assert (room.stroke, room.width, room.fill) == (GREY, 0.37, WHITE)
    assert room.bounds == pytest.approx((100, 50, 300, 150))
    assert (solid.fill_mode, solid.stroked, len(solid.rings)) == (FILL_EVEN_ODD, False, 2)
    assert (line.segments, line.fill_mode, line.width) == (2, FILL_NONE, 0.51)


def test_a_rotated_page_is_read_as_it_is_rendered() -> None:
    sheet = SheetPdf(600, 400)
    sheet.path(rect(100, 50, 300, 150), fill=WHITE)
    sheet.rotate(90)  # clockwise: the left edge becomes the top
    page = read_page(sheet.pdf())
    assert (page.width, page.height) == (400, 600)
    assert page.paths[0].bounds == pytest.approx((250, 100, 350, 300))


def test_each_text_object_keeps_its_own_text() -> None:
    sheet = SheetPdf()
    sheet.text("Küche", 120, 80)
    sheet.text("24.89 m²", 120, 80)  # drawn over the first: the page text would mix them
    page = read_page(sheet.pdf())
    assert [text.text for text in page.texts] == ["Küche", "24.89 m²"]
    assert page.texts[0].centre[1] == pytest.approx(78, abs=3)


# --------------------------------------------------------------------------- the scale


def bar(sheet: SheetPdf, left: float, block: float, label: str = "5") -> None:
    """A scale bar of three blocks, black-white-black, with its end label above it."""
    for at, fill in enumerate((BLACK, WHITE, BLACK)):
        sheet.path(rect(left + at * block, 370, left + (at + 1) * block, 375), width=0.5, fill=fill)
    sheet.text("0", left, 366)
    sheet.text(label, left + 3 * block - 2, 366)


def test_the_printed_ratio_gives_metres_per_point() -> None:
    sheet = SheetPdf()
    sheet.text("Maßstab 1:100 (A3)", 400, 380)
    scale, notes = read_scale(read_page(sheet.pdf()))
    assert (scale.status, scale.text, scale.evidence) == ("scaled", "1:100", ("scale_text",))
    assert scale.m_per_unit == pytest.approx(0.0352778, rel=1e-5)
    assert notes == ()


@pytest.mark.parametrize(
    "text", ["Plan 4 von 11:30 Uhr", "Ratio 2:100", "Sheet 1:100000", "v1.1:2"]
)
def test_other_numbers_with_a_colon_are_not_a_scale(text: str) -> None:
    sheet = SheetPdf()
    sheet.text(text, 400, 380)
    scale, _ = read_scale(read_page(sheet.pdf()))
    assert scale.status == "no_scale"


def test_a_scale_bar_that_agrees_is_listed_as_evidence() -> None:
    sheet = SheetPdf()
    sheet.text("1:100", 400, 380)
    bar(sheet, 100, 5 / M_PER_PT / 3)  # 5 m drawn at 1:100
    scale, notes = read_scale(read_page(sheet.pdf()))
    assert scale.evidence == ("scale_text", "scale_bar")
    assert scale.m_per_unit == pytest.approx(M_PER_PT)
    assert notes == ()


def test_a_scale_bar_that_disagrees_with_the_text_gives_the_scale() -> None:
    sheet = SheetPdf()
    sheet.text("1:100", 400, 380)
    bar(sheet, 100, 5 / M_PER_PT / 3 * 2)  # the bar is drawn at 1:50
    scale, notes = read_scale(read_page(sheet.pdf()))
    # the measured value over the text (the bar's corners are read to a tenth of a point)
    assert scale.m_per_unit == pytest.approx(M_PER_PT / 2, rel=1e-3)
    assert (scale.text, scale.evidence) == ("1:100", ("scale_text", "scale_bar"))
    assert len(notes) == 1 and "disagree by 50.0%; the bar is used" in notes[0]


@pytest.mark.parametrize(("stretch", "from_bar"), [(1.015, False), (1.025, True)])
def test_the_bar_replaces_the_text_only_beyond_the_two_percent_tolerance(
    stretch: float, from_bar: bool
) -> None:
    sheet = SheetPdf()
    sheet.text("1:100", 400, 380)
    bar(sheet, 100, 5 / M_PER_PT / 3 * stretch)
    scale, notes = read_scale(read_page(sheet.pdf()))
    expected = M_PER_PT / stretch if from_bar else M_PER_PT
    assert scale.m_per_unit == pytest.approx(expected, rel=1e-3)
    assert bool(notes) is from_bar


def test_a_scale_bar_alone_gives_the_scale() -> None:
    sheet = SheetPdf()
    bar(sheet, 100, 30, label="5 m")  # 5 m over 90 pt
    scale, _ = read_scale(read_page(sheet.pdf()))
    assert (scale.status, scale.text, scale.evidence) == ("scaled", None, ("scale_bar",))
    assert scale.m_per_unit == pytest.approx(5 / 90)


def test_legend_squares_are_not_a_scale_bar() -> None:
    sheet = SheetPdf()
    sheet.path(rect(40, 370, 46, 375), width=0.5, fill=BLACK)  # alone on its row
    sheet.path(rect(40, 340, 46, 345), width=0.5, fill=WHITE)
    sheet.text("5", 44, 366)
    scale, _ = read_scale(read_page(sheet.pdf()))
    assert scale.status == "no_scale"
    assert scale.evidence == ()


def test_a_row_of_white_boxes_is_not_a_scale_bar() -> None:
    sheet = SheetPdf()
    for left in (100, 130, 160):  # table cells: touching, but none is black
        sheet.path(rect(left, 370, left + 30, 375), width=0.5, fill=WHITE)
    sheet.text("5", 186, 366)
    scale, _ = read_scale(read_page(sheet.pdf()))
    assert scale.status == "no_scale"


# --------------------------------------------------------------------------- the swiss style


def swiss_room(
    sheet: SheetPdf, box: tuple[float, float, float, float], *lines: str, fill: int = 255
) -> None:
    """A room outline with its label lines (name, number, printed area) written inside."""
    sheet.path(rect(*box), stroke=GREY, width=0.37, fill=(fill, fill, fill))
    for at, line in enumerate(lines):
        sheet.text(line, box[0] + 4, box[1] + 10 + 8 * at)


def swiss_window(sheet: SheetPdf, box: tuple[float, float, float, float], degrees: float) -> None:
    """A window symbol: a white rectangle with two lines along it, turned about its centre."""
    x0, y0, x1, y1 = box
    centre = ((x0 + x1) / 2, (y0 + y1) / 2)
    sheet.path(turned(rect(*box), degrees, centre), width=0.51, fill=WHITE)
    for y in (y0 + 1, y1 - 1):
        sheet.path(turned([(x0, y), (x1, y)], degrees, centre), width=0.37)


def swiss_sheet() -> SheetPdf:
    sheet = SheetPdf(600, 400)
    swiss_room(sheet, (100, 50, 300, 150), "Küche", "2.01", "22.40 m²")  # net of the Reduit
    swiss_room(sheet, (150, 80, 200, 120), "Reduit", "2.02", "2.49 m²")  # inside the kitchen
    swiss_room(sheet, (300, 50, 400, 150), "Bad", "2.03", "12.45 m²")
    swiss_room(sheet, (100, 150, 300, 200), "Balkon", "2.04", "12.45 m²", fill=228)
    swiss_room(sheet, (400, 50, 450, 150), "Lift", "2.05", fill=243)
    swiss_room(sheet, (450, 50, 550, 150), "Zimmer", "3.01")  # the next apartment
    sheet.text("Whg. A", 104, 142)  # in the kitchen
    sheet.text("Whg. B", 454, 142)
    sheet.path(rect(98, 48, 452, 202), stroke=RED, width=1.28)  # unit A, lift included
    sheet.path(rect(449, 48, 552, 152), stroke=RED, width=1.28)
    sheet.path(rect(296, 90, 304, 110), stroke=DOOR_GREY, width=0.37)
    sheet.path(rect(396, 90, 404, 110), stroke=DOOR_GREY, width=0.37)
    swiss_window(sheet, (120, 46, 180, 52), degrees=0)
    swiss_window(sheet, (480, 160, 540, 166), degrees=30)  # plans are rotated
    lift = rect(410, 60, 440, 90)  # a white rectangle with crossing diagonals: not a window
    sheet.path(lift, width=0.51, fill=WHITE)
    sheet.path([(410, 60), (440, 90)], width=0.37)
    sheet.path([(440, 60), (410, 90)], width=0.37)
    sheet.path(ring(320, 70, 6, 48), width=0.51)  # toilet: a basin outline with its tank line
    sheet.path([(316, 62), (324, 62)], width=0.51)
    sheet.path(ring(340, 70, 6, 48), width=0.51)  # washbasin
    sheet.path(ring(360, 120, 10, 69), width=0.51)  # bathtub
    sheet.path(rect(375, 60, 395, 80), width=0.51)  # shower: stroke only
    sheet.path(ring(40, 300, 6, 48), width=0.5)  # the legend draws its symbols thinner
    sheet.text("Massstab 1:100 (A3)", 450, 380)
    return sheet


def test_swiss_symbols_are_told_apart_by_stroke_and_segments() -> None:
    found = extract(swiss_sheet().pdf())
    assert Counter(element.class_ for element in found.elements) == {
        "door": 2,
        "window": 2,
        "toilet": 1,
        "sink": 1,
        "bathtub": 1,
        "shower": 1,
    }
    toilet = next(element for element in found.elements if element.class_ == "toilet")
    assert toilet.box == pytest.approx((314 / 600, 64 / 400, 326 / 600, 76 / 400), abs=1e-3)
    assert all(element.plan == "p1" and element.page == 1 for element in found.elements)
    # What the swiss rules look for: a class outside this list was not read, so it has no count.
    assert found.read == ("door", "window", "toilet", "sink", "bathtub", "shower", "room")
    assert {element.class_ for element in found.elements} < set(found.read or ())


def test_swiss_rooms_have_number_label_type_and_net_area() -> None:
    found = extract(swiss_sheet().pdf())
    rooms = {room.attrs["number"]: room for room in found.rooms}
    assert list(rooms) == ["2.01", "2.02", "2.03", "2.04", "2.05", "3.01"]
    assert [room.type for room in rooms.values()] == [
        "kitchen", "storage", "bathroom", "balcony", "shaft", "bedroom",
    ]  # fmt: skip
    assert [room.label for room in rooms.values()] == [
        "Küche", "Reduit", "Bad", "Balkon", "Lift", "Zimmer",
    ]  # fmt: skip
    kitchen = rooms["2.01"]
    # the storage room drawn inside the kitchen is not kitchen floor
    assert kitchen.area_m2 == pytest.approx(area_m2(200, 100) - area_m2(50, 40), abs=0.002)
    assert kitchen.attrs["cutouts"] == 1
    assert kitchen.box == pytest.approx((100 / 600, 50 / 400, 300 / 600, 150 / 400), abs=1e-5)
    assert kitchen.polygon is not None and len(kitchen.polygon) == 4
    assert rooms["2.02"].area_m2 == pytest.approx(area_m2(50, 40), abs=0.002)
    assert [room.outdoor for room in rooms.values()] == [False, False, False, True, False, False]
    assert rooms["2.04"].attrs["fill"] == 228


def test_a_swiss_apartment_is_the_rooms_inside_its_unit_outline() -> None:
    found = extract(swiss_sheet().pdf())
    rooms = {room.attrs["number"]: room for room in found.rooms}
    assert [rooms[n].apartment for n in ("2.01", "2.02", "2.03", "2.04", "2.05", "3.01")] == [
        "aA", "aA", "aA", "aA", "aA", "aB",
    ]  # fmt: skip
    a, b = found.apartments
    assert (a.id, a.label, b.id, b.label) == ("aA", "A", "aB", "B")
    # kitchen net + storage + bath; the balcony (outdoor) and the lift (fill 243) stay out
    assert a.area_m2 == pytest.approx(area_m2(200, 100) + area_m2(100, 100), abs=0.003)
    assert b.area_m2 == pytest.approx(area_m2(100, 100), abs=0.002)


def test_a_swiss_sheet_has_one_plan_around_its_rooms() -> None:
    found = extract(swiss_sheet().pdf())
    (plan,) = found.plans
    assert plan.box == pytest.approx((100 / 600, 50 / 400, 550 / 600, 200 / 400), abs=1e-5)
    assert found.method == "parser"


def test_a_room_drawn_as_one_path_with_a_hole_loses_the_hole() -> None:
    sheet = SheetPdf()
    sheet.path(
        rect(100, 50, 300, 150), rect(150, 80, 200, 120), stroke=GREY, width=0.37, fill=WHITE
    )
    sheet.text("Wohnen", 104, 60)
    sheet.text("1.01", 104, 68)
    sheet.text("1:100", 450, 380)
    (room,) = extract(sheet.pdf()).rooms
    assert room.area_m2 == pytest.approx(area_m2(200, 100) - area_m2(50, 40), abs=0.002)
    assert room.type == "living"


def test_without_a_scale_swiss_rooms_are_listed_with_unknown_areas() -> None:
    sheet = SheetPdf()
    swiss_room(sheet, (100, 50, 300, 150), "Küche", "2.01")
    sheet.text("Whg. A", 104, 142)
    sheet.path(rect(98, 48, 302, 152), stroke=RED, width=1.28)
    found = extract(sheet.pdf())
    assert found.scale.status == "no_scale"
    assert [(room.type, room.area_m2) for room in found.rooms] == [("kitchen", None)]
    assert [(apartment.id, apartment.area_m2) for apartment in found.apartments] == [("aA", None)]


@pytest.mark.parametrize(
    ("name", "fill", "expected"),
    [
        (None, 228, ("outdoor", True)),  # an unnamed balcony strip: the grey says outdoor
        ("Loggia", 255, ("outdoor", True)),
        ("Balcone", 228, ("balcony", True)),
        (None, 243, ("shaft", False)),
        ("Treppenhaus", 255, ("shaft", False)),
        ("Zimmer", 243, ("bedroom", False)),  # a named room keeps its name's type
        ("Pièce", 255, ("bedroom", False)),  # a lone "room" is a flat's bedroom, in each language
        ("Stanza", 255, ("bedroom", False)),
        ("Séjour/repas", 255, ("living", False)),
        (None, 255, ("other", False)),
    ],
)
def test_swiss_room_type_comes_from_the_label_and_the_fill(
    name: str | None, fill: int, expected: tuple[str, bool]
) -> None:
    assert swiss.room_type(name, fill) == expected


def test_a_room_without_a_number_is_not_listed() -> None:
    sheet = SheetPdf()
    swiss_room(sheet, (100, 50, 300, 150), "Küche")
    assert extract(sheet.pdf()).rooms == ()


def test_each_tank_line_makes_one_basin_outline_a_toilet() -> None:
    sheet = SheetPdf()
    swiss_room(sheet, (100, 50, 300, 150), "Bad", "1.01")
    for x in (120, 160, 200):
        sheet.path(ring(x, 100, 6, 48), width=0.51)
    sheet.path([(116, 92), (124, 92)], width=0.51)  # inside the first outline's box
    sheet.path([(210, 100), (214, 100)], width=0.51)  # beside the third, not inside any
    found = extract(sheet.pdf())
    assert Counter(element.class_ for element in found.elements) == {"toilet": 2, "sink": 1}
    sink = next(element for element in found.elements if element.class_ == "sink")
    assert sink.box[0] == pytest.approx(154 / 600, abs=1e-3)  # the middle outline is left


# --------------------------------------------------------------------------- the IFC render style


def ifc_room(sheet: SheetPdf, rings: list[list[Point]], *lines: str) -> None:
    sheet.twin(*rings, fill=SPACE, stroke=SPACE_EDGE, width=0.12)
    x, y = rings[0][0]
    for at, line in enumerate(lines):
        sheet.text(line, x + 4, y + 10 + 8 * at)


def ifc_door(sheet: SheetPdf, x: float, y: float) -> None:
    """A door as the renderer draws one: two jambs that do not touch, then the open leaf."""
    for jamb_x in (x, x + 26):
        sheet.path(
            rect(jamb_x, y, jamb_x + 2, y + 6), rect(jamb_x, y + 7, jamb_x + 2, y + 9), width=0.13
        )
    sheet.path(rect(x + 2, y - 24, x + 4, y), width=0.13)


def ifc_sheet() -> SheetPdf:
    sheet = SheetPdf(600, 400)
    sheet.path(rect(0, 0, 600, 400), stroke=None, fill=WHITE)  # the page background
    ifc_room(sheet, [rect(100, 50, 300, 150)], "Kitchen", "1.2")
    ifc_room(sheet, [rect(300, 50, 500, 150), rect(380, 80, 420, 120)], "Corridor", "1.1")
    sheet.twin(rect(98, 46, 502, 50), fill=SOLID, stroke=BLACK, width=0.15)  # wall
    sheet.twin(rect(296, 50, 300, 150), fill=SOLID, stroke=BLACK, width=0.15)
    sheet.twin(rect(385, 85, 395, 95), fill=SOLID, stroke=BLACK, width=0.15)  # a column
    for left in (120, 180):  # two windows in a strip: frame, then the panes drawn on it
        sheet.twin(rect(left, 45, left + 60, 51), fill=WHITE, stroke=BLACK, width=0.1)
        sheet.twin(rect(left + 2, 47, left + 58, 49), fill=WHITE, stroke=BLACK, width=0.1)
        sheet.twin(rect(left, 51, left + 60, 53), fill=WHITE, stroke=BLACK, width=0.1)  # sill
    ifc_door(sheet, 200, 150)
    ifc_door(sheet, 210, 152)  # the next door overlaps the first one's box
    sheet.path(rect(520, 60, 560, 140), stroke=(51, 51, 51), width=0.1)  # a stair flight
    sheet.text("Demo house — Floor plan: Level 1", 20, 360)
    sheet.text("Scale 1:200 · cut at 1.20 m above storey level", 20, 372)
    return sheet


def test_ifc_rooms_have_label_type_and_drawn_area() -> None:
    found = extract(ifc_sheet().pdf())
    kitchen, corridor = found.rooms
    assert (kitchen.label, kitchen.type) == ("Kitchen 1.2", "kitchen")
    assert kitchen.attrs == {"number": "1.2", "name": "Kitchen"}
    assert kitchen.area_m2 == pytest.approx(200 * 100 * (2 * M_PER_PT) ** 2, abs=0.002)
    assert (corridor.label, corridor.type) == ("Corridor 1.1", "hall")
    # the inner ring of the corridor's path is a hole (even-odd)
    assert corridor.area_m2 == pytest.approx((200 * 100 - 40 * 40) * (2 * M_PER_PT) ** 2, abs=0.002)
    assert corridor.box == pytest.approx((0.5, 0.125, 500 / 600, 0.375), abs=1e-5)


def test_an_ifc_sheet_says_it_was_read_for_rooms_walls_windows_and_doors() -> None:
    found = extract(ifc_sheet().pdf())
    assert found.read == ("room", "wall", "window", "door")
    assert {element.class_ for element in found.elements} < set(found.read or ())


def test_ifc_scale_and_storey_come_from_the_sheet_text() -> None:
    found = extract(ifc_sheet().pdf())
    assert (found.scale.status, found.scale.text) == ("scaled", "1:200")
    assert found.scale.m_per_unit == pytest.approx(2 * M_PER_PT, rel=1e-5)
    (plan,) = found.plans
    assert plan.storey == "Level 1"


def test_ifc_cut_solids_are_walls_and_the_note_says_columns_are_among_them() -> None:
    found = extract(ifc_sheet().pdf())
    walls = [element for element in found.elements if element.class_ == "wall"]
    assert len(walls) == 3
    assert walls[0].polygon is not None and len(walls[0].polygon) == 4
    assert any("3 cut solids are listed as walls" in note for note in found.notes)


def test_ifc_window_pieces_are_one_window_and_a_strip_is_several() -> None:
    found = extract(ifc_sheet().pdf())
    windows = [element for element in found.elements if element.class_ == "window"]
    assert [window.box for window in windows] == [
        pytest.approx((120 / 600, 45 / 400, 180 / 600, 53 / 400), abs=1e-5),
        pytest.approx((180 / 600, 45 / 400, 240 / 600, 53 / 400), abs=1e-5),
    ]


def test_ifc_doors_are_split_by_drawing_order_not_by_position() -> None:
    found = extract(ifc_sheet().pdf())
    doors = [element for element in found.elements if element.class_ == "door"]
    assert [door.box for door in doors] == [
        pytest.approx((200 / 600, 126 / 400, 228 / 600, 159 / 400), abs=1e-5),
        pytest.approx((210 / 600, 128 / 400, 238 / 600, 161 / 400), abs=1e-5),
    ]


def test_the_two_styles_are_recognised_by_what_they_draw() -> None:
    swiss_page, ifc_page = read_page(swiss_sheet().pdf()), read_page(ifc_sheet().pdf())
    assert (swiss.matches(swiss_page), ifc_render.matches(swiss_page)) == (True, False)
    assert (swiss.matches(ifc_page), ifc_render.matches(ifc_page)) == (False, True)


# --------------------------------------------------------------------------- the extractor


def test_the_png_of_a_sheet_gets_the_same_fractions_and_its_own_scale() -> None:
    pdf = swiss_sheet().pdf()
    on_pdf = extract(pdf)
    on_png = extract(pdf, Page(page=1, width=1200, height=800, unit="px"))  # rendered at 2x
    assert on_png.elements == on_pdf.elements
    assert on_png.rooms == on_pdf.rooms
    assert on_pdf.scale.m_per_unit == pytest.approx(M_PER_PT, rel=1e-5)
    assert on_png.scale.m_per_unit == pytest.approx(M_PER_PT / 2, rel=1e-5)


def test_a_sheet_of_another_shape_is_not_the_pdf_rendered() -> None:
    found = extract(swiss_sheet().pdf(), Page(page=1, width=1000, height=1000, unit="px"))
    assert (found.elements, found.rooms, found.scale.status) == ((), (), "no_scale")
    assert "is not page 1 of data/demo/plan.pdf rendered" in found.notes[0]
    assert found.read == ()


def test_a_pdf_in_no_known_style_gets_its_scale_and_a_note() -> None:
    sheet = SheetPdf()
    sheet.path(rect(100, 50, 300, 150), width=2.0)
    sheet.text("Scale 1:50", 450, 380)
    found = extract(sheet.pdf())
    assert (found.scale.status, found.scale.text) == ("scaled", "1:50")
    assert (found.elements, found.rooms, found.plans) == ((), (), ())
    assert "no sheet style we have reading rules for" in found.notes[0]
    assert found.read == ()  # only the scale was read: no class has a count


def test_only_the_first_page_is_read_and_the_note_says_so() -> None:
    sheet = swiss_sheet()
    sheet.add_page()
    found = extract(sheet.pdf())
    assert len(found.rooms) == 6
    assert "only page 1 of 2 was read" in found.notes


def test_a_source_that_is_not_a_pdf_is_left_alone() -> None:
    source = DrawingFile(path="data/demo/plan.svg", size=1, sha256="0" * 64, kind="svg")
    sheet = Sheet(file=source, pages=(Page(page=1, width=600, height=400, unit="pt"),))
    found = PdfVectorExtractor(Files({})).extract(source, sheet)  # reading would raise KeyError
    assert found.elements == ()
    assert "is svg, not a PDF" in found.notes[0]
    assert found.read == ()


# --------------------------------------------------------------------------- the second counter


def test_the_second_counter_gives_the_area_printed_in_each_room_under_the_extractors_id() -> None:
    pdf = swiss_sheet().pdf()
    rooms = {room.id: room for room in extract(pdf).rooms}
    again = measure_again(pdf)
    # No scale bar on this sheet, so the scale has one reading and is not measured twice.
    assert {one.quantity for one in again} == {"room_area"}
    printed = {one.subject.ref or "": one.value for one in again}
    assert {ref: value.value for ref, value in printed.items()} == {
        "r1": 22.40,  # Küche 2.01
        "r2": 2.49,
        "r3": 12.45,
        "r4": 12.45,
    }  # the lift and the next apartment's room print no area
    assert [rooms[ref].attrs["number"] for ref in printed] == ["2.01", "2.02", "2.03", "2.04"]
    for ref, value in printed.items():
        assert (value.method, value.unit, value.page) == ("printed_label", "m2", 1)
        x0, y0, x1, y1 = rooms[ref].box
        assert value.box is not None  # the label lies in its room
        assert (
            x0 <= value.box[0] and value.box[2] <= x1 and y0 <= value.box[1] and value.box[3] <= y1
        )
        assert value.value == pytest.approx(rooms[ref].area_m2, rel=0.002)


def test_a_printed_area_with_a_decimal_comma_is_read() -> None:
    sheet = SheetPdf(600, 400)
    swiss_room(sheet, (300, 50, 400, 150), "Bad", "2.03", "12,45 m²")
    (area,) = measure_again(sheet.pdf())
    assert (area.subject.ref, area.value.value) == ("r1", 12.45)


def test_the_second_counter_reads_the_scale_from_the_text_and_from_the_bar() -> None:
    sheet = swiss_sheet()
    bar(sheet, 100, 5 / M_PER_PT / 3 * 2)  # drawn at 1:50; the sheet says 1:100
    text, drawn = (one for one in measure_again(sheet.pdf()) if one.quantity == "scale")
    assert (text.subject.kind, text.subject.ref) == ("sheet", None)
    assert (text.value.method, text.value.unit) == ("scale_text", "m/pt")
    assert text.value.value == pytest.approx(M_PER_PT, rel=1e-4)
    assert text.value.box is not None  # where "Massstab 1:100 (A3)" was written
    assert text.value.box[0] == pytest.approx(450 / 600, abs=0.01)
    assert 360 / 400 < text.value.box[1] < text.value.box[3] < 390 / 400
    assert (drawn.value.method, drawn.value.unit) == ("scale_bar", "m/pt")
    assert drawn.value.value == pytest.approx(M_PER_PT / 2, rel=1e-3)
    assert drawn.value.box == pytest.approx(
        (100 / 600, 370 / 400, (100 + 10 / M_PER_PT) / 600, 375 / 400), abs=1e-4
    )


def test_the_second_counter_measures_a_png_in_its_own_pixels() -> None:
    sheet = swiss_sheet()
    bar(sheet, 100, 5 / M_PER_PT / 3)
    pdf = sheet.pdf()
    on_png = measure_again(pdf, Page(page=1, width=1200, height=800, unit="px"))  # at 2x
    on_pdf = measure_again(pdf)
    scales = [one.value for one in on_png if one.quantity == "scale"]
    assert [value.unit for value in scales] == ["m/px", "m/px"]
    assert [value.value for value in scales] == pytest.approx([M_PER_PT / 2] * 2, rel=1e-3)
    # areas are in m² and boxes are page fractions: the same on the render
    assert [one for one in on_png if one.quantity == "room_area"] == [
        one for one in on_pdf if one.quantity == "room_area"
    ]


def test_the_second_counter_measures_nothing_on_a_sheet_that_is_not_the_pdf() -> None:
    sheet = swiss_sheet()
    bar(sheet, 100, 5 / M_PER_PT / 3)
    assert measure_again(sheet.pdf(), Page(page=1, width=1000, height=1000, unit="px")) == []
    source = DrawingFile(path="data/demo/plan.svg", size=1, sha256="0" * 64, kind="svg")
    own = Sheet(file=source, pages=(Page(page=1, width=600, height=400, unit="pt"),))
    assert PdfSecondCounter(Files({})).measure(source, own) == []  # reading would raise KeyError


@pytest.mark.parametrize("page", [None, Page(page=1, width=1200, height=800, unit="px")])
def test_the_ifc_second_counter_gives_a_sheet_without_a_model_every_reading_of_the_pdf_one(
    page: Page | None,
) -> None:
    """`SECOND_COUNTER=ifc`, the default, on a swiss sheet and on its PNG: the scale as printed
    and as the bar measures it, and the area printed in each room, exactly as `pdf` gives them."""
    sheet = swiss_sheet()
    bar(sheet, 100, 5 / M_PER_PT / 3 * 2)
    pdf = sheet.pdf()
    source, on = source_and_sheet(pdf, page)
    files = Files({source.path: pdf})
    readings = IfcSecondCounter(files, IfcModels(files), PdfSecondCounter(files)).measure(
        source, on
    )
    assert readings == measure_again(pdf, page)
    assert Counter(one.quantity for one in readings) == {"scale": 2, "room_area": 4}
    assert {one.value.method for one in readings} == {"scale_text", "scale_bar", "printed_label"}


def test_an_ifc_sheet_prints_no_room_area_to_compare() -> None:
    assert measure_again(ifc_sheet().pdf()) == []


def ingested(tmp_path: Path, sheet: SheetPdf) -> dict[str, Any]:
    """The extraction_v1 JSON the pipeline writes for `sheet`, with the default adapters."""
    dataset, out, pdf = tmp_path / "dataset", tmp_path / "out", "data/demo/plan.pdf"
    (dataset / "data" / "demo").mkdir(parents=True)
    (dataset / pdf).write_bytes(sheet.pdf())
    build_pipeline(Settings(), dataset).ingest([pdf], ExtractionV1Writer(out, {pdf: "dev"}))
    written = json.loads((out / "demo" / "plan.pdf.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert list(validator.iter_errors(written)) == []
    return written


def test_a_printed_area_that_disagrees_with_the_outline_is_a_conflict_and_the_label_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # so a developer's backend/.env can't change the result
    sheet = SheetPdf(600, 400)
    swiss_room(sheet, (100, 50, 300, 150), "Küche", "2.01", "30.00 m²")  # the outline is 24.89
    swiss_room(sheet, (300, 50, 400, 150), "Bad", "2.02", "12.45 m²")
    swiss_room(sheet, (400, 50, 450, 150), "Zimmer", "2.03")  # prints no area
    sheet.text("Massstab 1:100 (A3)", 450, 380)

    written = ingested(tmp_path, sheet)

    kitchen, bath = written["conflicts"]
    assert (kitchen["id"], kitchen["quantity"], kitchen["status"]) == (
        "c1",
        "room_area",
        "conflict",
    )
    assert kitchen["subject"] == {"kind": "room", "ref": "r1"}
    assert [(value["method"], value["value"]) for value in kitchen["values"]] == [
        ("polygon_x_scale", pytest.approx(area_m2(200, 100), abs=0.002)),
        ("printed_label", 30.0),
    ]
    assert kitchen["resolution"] == {
        "rule": "the printed label over the outline at the sheet's scale",
        "value": 30.0,
    }
    assert (bath["status"], bath["resolution"]) == (
        "agree",
        {"rule": "both methods agree", "value": 12.45},
    )
    areas = {room["id"]: room["area_m2"] for room in written["rooms"]}
    assert areas["r1"] == 30.0  # the drawing carries the value its conflict resolves to
    assert areas["r2"] == pytest.approx(area_m2(100, 100), abs=0.002)  # agreed: as measured
    assert areas["r3"] == pytest.approx(area_m2(50, 100), abs=0.002)


def test_a_bar_that_disagrees_with_the_text_is_a_conflict_and_the_areas_use_the_bar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    sheet = SheetPdf(600, 400)
    swiss_room(sheet, (100, 50, 300, 150), "Zimmer", "2.01")
    sheet.text("Massstab 1:100 (A3)", 450, 380)
    bar(sheet, 100, 5 / M_PER_PT / 3 * 2)  # drawn at 1:50

    written = ingested(tmp_path, sheet)

    (scale,) = written["conflicts"]
    assert (scale["quantity"], scale["subject"]) == ("scale", {"kind": "sheet", "ref": None})
    assert (scale["status"], scale["tolerance"]) == ("conflict", 0.02)
    assert [(value["method"], value["value"]) for value in scale["values"]] == [
        ("scale_text", pytest.approx(M_PER_PT, rel=1e-4)),
        ("scale_bar", pytest.approx(M_PER_PT / 2, rel=1e-3)),
    ]
    assert scale["resolution"] == {
        "rule": "the measured scale bar over the scale text",
        "value": scale["values"][1]["value"],
    }
    # The drawing's scale is the resolved one, and so is the room area: a quarter of 1:100's.
    assert written["scale"]["m_per_unit"] == scale["resolution"]["value"]
    assert written["rooms"][0]["area_m2"] == pytest.approx(area_m2(200, 100) / 4, rel=2e-3)


def test_a_bar_that_agrees_with_the_text_is_listed_and_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    sheet = SheetPdf(600, 400)
    swiss_room(sheet, (100, 50, 300, 150), "Zimmer", "2.01")
    sheet.text("Massstab 1:100 (A3)", 450, 380)
    bar(sheet, 100, 5 / M_PER_PT / 3 * 1.01)  # 1% off: within the tolerance

    written = ingested(tmp_path, sheet)

    (scale,) = written["conflicts"]
    assert (scale["quantity"], scale["status"]) == ("scale", "agree")
    assert scale["resolution"]["rule"] == "both methods agree"
    assert written["scale"]["m_per_unit"] == pytest.approx(M_PER_PT, rel=1e-4)  # the text's value
    assert written["rooms"][0]["area_m2"] == pytest.approx(area_m2(200, 100), abs=0.002)


def test_the_setting_wires_it_and_a_plan_as_pdf_and_png_gives_two_valid_extractions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # so a developer's backend/.env can't change the result
    monkeypatch.setenv("EXTRACTOR_VECTOR", "pdf")
    dataset, out = tmp_path / "dataset", tmp_path / "out"
    (dataset / "data" / "demo").mkdir(parents=True)
    sheet = swiss_sheet()
    pdf, png = "data/demo/plan.pdf", "data/demo/plan.png"
    (dataset / pdf).write_bytes(sheet.pdf())
    (dataset / png).write_bytes(sheet.png(scale=2))

    pipeline = build_pipeline(Settings(), dataset)
    report = pipeline.ingest([png, pdf], ExtractionV1Writer(out, {pdf: "dev", png: "dev"}))

    assert [(s.file, s.route, s.source) for s in report.sheets] == [
        (png, "vector", pdf),  # the PNG is read from the PDF of the same plan
        (pdf, "vector", pdf),
    ]
    validator = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    on_png = json.loads((out / "demo" / "plan.png.json").read_text(encoding="utf-8"))
    on_pdf = json.loads((out / "demo" / "plan.pdf.json").read_text(encoding="utf-8"))
    for written in (on_png, on_pdf):
        assert list(validator.iter_errors(written)) == []
        assert len(written["rooms"]) == 6
        assert written["scale"]["status"] == "scaled"
        assert written["read"] == ["door", "window", "toilet", "sink", "bathtub", "shower", "room"]
        # every printed room area was compared with its outline, and all four agree
        assert [(c["quantity"], c["status"]) for c in written["conflicts"]] == [
            ("room_area", "agree")
        ] * 4
    assert on_png["elements"] == on_pdf["elements"]
    assert on_png["pages"][0]["unit"] == "px"
    assert on_png["scale"]["m_per_unit"] == pytest.approx(
        on_pdf["scale"]["m_per_unit"] / 2, rel=1e-4
    )
