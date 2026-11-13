"""The vector route's PDF extractor (`EXTRACTOR_VECTOR=pdf`) on synthetic sheets drawn in the two
styles it has reading rules for. Each test names the rule it holds in place."""

import json
import math
from collections import Counter
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pdf_sheets import BLACK, WHITE, Point, SheetPdf, rect, ring

from app.adapters.extraction_v1 import ExtractionV1Writer
from app.adapters.vector_pdf import PdfVectorExtractor, ifc_render, swiss
from app.adapters.vector_pdf.objects import FILL_EVEN_ODD, FILL_NONE, FILL_WINDING, read_page
from app.adapters.vector_pdf.scale import M_PER_PT_ON_PAPER, read_scale
from app.composition import build_pipeline
from app.core.drawing.model import Page
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
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


def extract(pdf: bytes, sheet_page: Page | None = None, sheet_kind: str = "pdf") -> Extracted:
    """Run the extractor on `pdf`, placing the result on the PDF itself or on another sheet."""
    source = DrawingFile(path="data/demo/plan.pdf", size=len(pdf), sha256="0" * 64, kind="pdf")
    if sheet_page is None:
        page = read_page(pdf)
        sheet = Sheet(
            file=source, pages=(Page(page=1, width=page.width, height=page.height, unit="pt"),)
        )
    else:
        other = source.model_copy(update={"path": f"data/demo/plan.{sheet_kind}", "kind": "png"})
        sheet = Sheet(file=other, pages=(sheet_page,))
    return PdfVectorExtractor(Files({source.path: pdf})).extract(source, sheet)


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


def test_a_scale_bar_that_disagrees_with_the_text_is_reported() -> None:
    sheet = SheetPdf()
    sheet.text("1:100", 400, 380)
    bar(sheet, 100, 5 / M_PER_PT / 3 * 2)  # the bar is drawn at 1:50
    scale, notes = read_scale(read_page(sheet.pdf()))
    assert scale.m_per_unit == pytest.approx(M_PER_PT)  # the text gives the value
    assert len(notes) == 1 and "disagree" in notes[0]


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
    swiss_room(sheet, (100, 50, 300, 150), "Küche", "2.01", "24.89 m²")
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


def test_swiss_rooms_have_number_label_type_and_net_area() -> None:
    found = extract(swiss_sheet().pdf())
    rooms = {room.attrs["number"]: room for room in found.rooms}
    assert list(rooms) == ["2.01", "2.02", "2.03", "2.04", "2.05", "3.01"]
    assert [room.type for room in rooms.values()] == [
        "kitchen", "storage", "bathroom", "balcony", "shaft", "other",
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
        ("Zimmer", 243, ("other", False)),  # a named room keeps its name's type
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


def test_a_pdf_in_no_known_style_gets_its_scale_and_a_note() -> None:
    sheet = SheetPdf()
    sheet.path(rect(100, 50, 300, 150), width=2.0)
    sheet.text("Scale 1:50", 450, 380)
    found = extract(sheet.pdf())
    assert (found.scale.status, found.scale.text) == ("scaled", "1:50")
    assert (found.elements, found.rooms, found.plans) == ((), (), ())
    assert "no sheet style we have reading rules for" in found.notes[0]


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
    assert on_png["elements"] == on_pdf["elements"]
    assert on_png["pages"][0]["unit"] == "px"
    assert on_png["scale"]["m_per_unit"] == pytest.approx(
        on_pdf["scale"]["m_per_unit"] / 2, rel=1e-4
    )
