"""Schedules read from a drawn PDF sheet (TABLES=pdf): a ruled grid with a title row, a header
with group headings and tall cells, blank cells, a list drawn as stacked boxes, and boxes
without a title that are no schedule. The sheets are drawn here; no partner data."""

import ctypes
from pathlib import Path

import pytest
from pdf_sheets import SheetPdf
from pypdfium2 import raw

from app.adapters.pdf_tables import PdfTables
from app.adapters.pdf_tables.lattice import read_tables
from app.adapters.pdf_tables.page import read_table_page
from app.adapters.vector_pdf import PdfVectorExtractor
from app.composition import build_pipeline
from app.core.drawing.model import Element, Page, Scale, Table
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.settings import Settings

Edge = tuple[int, int]

# The door schedule: title, then "Door" over Width and Height; Mark, Matl and Notes are one cell
# two header rows tall. Body rows are 12 pt.
DOOR_XS = (20.0, 80.0, 140.0, 200.0, 260.0, 320.0)
DOOR_YS = (20.0, 35.0, 50.0, 65.0, 77.0, 89.0, 101.0)
DOOR_ROWS = (
    ("101", "11", "7'-0\"", "WD-1", "A"),
    ("102", "3'-0\"", "7'-0\"", None, None),
    ("111", "2'-8\"", "7'-0\"", "AL-1", "A, B"),
)
KEY_XS = (350.0, 400.0, 440.0, 560.0)


def ruled(
    sheet: SheetPdf,
    xs: tuple[float, ...],
    ys: tuple[float, ...],
    *,
    no_across: frozenset[Edge] = frozenset(),
    no_down: frozenset[Edge] = frozenset(),
) -> None:
    """Every cell edge as its own line, the way Revit draws a schedule. `no_across` holds
    (y index, column) of horizontal edges left out, `no_down` (row, x index) of vertical ones."""
    for k, y in enumerate(ys):
        for j in range(len(xs) - 1):
            if (k, j) not in no_across:
                sheet.path([(xs[j], y), (xs[j + 1], y)])
    for i in range(len(ys) - 1):
        for k, x in enumerate(xs):
            if (i, k) not in no_down:
                sheet.path([(x, ys[i]), (x, ys[i + 1])])


def put(sheet: SheetPdf, text: str, x0: float, y1: float) -> None:
    """Text on the bottom of a cell starting at x0 + 2."""
    sheet.text(text, x0 + 2, y1 - 3)


def door_schedule(sheet: SheetPdf) -> None:
    inner = range(1, len(DOOR_XS) - 1)
    ruled(
        sheet,
        DOOR_XS,
        DOOR_YS,
        # the title row is one cell; "Door" covers columns 1-2; Mark, Matl, Notes are two rows
        no_down=frozenset({(0, k) for k in inner} | {(1, 2)}),
        no_across=frozenset({(2, 0), (2, 3), (2, 4)}),
    )
    put(sheet, "DOOR SCHEDULE", 120, 35)
    put(sheet, "Mark", DOOR_XS[0], 65)
    put(sheet, "Door", 100, 50)
    put(sheet, "Width", DOOR_XS[1], 65)
    put(sheet, "Height", DOOR_XS[2], 65)
    put(sheet, "Matl", DOOR_XS[3], 65)
    put(sheet, "Notes", DOOR_XS[4], 65)
    for row, bottom in zip(DOOR_ROWS, DOOR_YS[4:], strict=True):
        for cell, x0 in zip(row, DOOR_XS, strict=False):
            if cell is not None:
                put(sheet, cell, x0, bottom)


def keynotes(sheet: SheetPdf) -> None:
    """A title and header box, then two body boxes a gap apart; one note wraps to two lines."""
    ruled(sheet, KEY_XS, (20.0, 35.0, 50.0), no_down=frozenset({(0, 1), (0, 2)}))
    put(sheet, "KEYNOTES", 420, 35)
    for text, x0 in zip(("Category", "Key", "Note"), KEY_XS, strict=False):
        put(sheet, text, x0, 50)
    ruled(sheet, KEY_XS, (56.0, 68.0, 88.0))
    for row, bottom in ((("DOOR", "GL-1", "GLASS"), 68.0), (("DOOR", "WD-1", "SOLID"), 80.0)):
        for text, x0 in zip(row, KEY_XS, strict=False):
            put(sheet, text, x0, bottom)
    put(sheet, "CORE", KEY_XS[2], 88.0)  # the second line of "SOLID CORE"
    ruled(sheet, KEY_XS, (94.0, 106.0))
    for text, x0 in zip(("FRAME", "AL-1", "ALUMINIUM"), KEY_XS, strict=False):
        put(sheet, text, x0, 106.0)


def untitled_boxes(sheet: SheetPdf) -> None:
    """A revision list: header and rows, but no title row."""
    xs, ys = (350.0, 380.0, 500.0, 560.0), (200.0, 215.0, 227.0, 239.0)
    ruled(sheet, xs, ys)
    for row, bottom in zip(
        (("No.", "Description", "Date"), ("1", "PERMIT", "08.18"), ("2", "ADDENDUM", "02.10")),
        ys[1:],
        strict=True,
    ):
        for text, x0 in zip(row, xs, strict=False):
            put(sheet, text, x0, bottom)


def schedules_pdf() -> bytes:
    sheet = SheetPdf()
    door_schedule(sheet)
    keynotes(sheet)
    untitled_boxes(sheet)
    return sheet.pdf()


def tables_of(pdf: bytes) -> list[Table]:
    return read_tables(read_table_page(pdf))


def by_title(tables: list[Table]) -> dict[str | None, Table]:
    return {table.title: table for table in tables}


def test_a_ruled_schedule_gives_title_header_and_rows() -> None:
    door = by_title(tables_of(schedules_pdf()))["DOOR SCHEDULE"]
    assert door.columns == ("Mark", "Door Width", "Door Height", "Matl", "Notes")
    assert [row.cells for row in door.rows] == list(DOOR_ROWS)
    assert door.key_column == 0
    assert door.page == 1
    # page fractions of the 600 x 400 sheet: the table from its title row down
    assert door.box == pytest.approx((20 / 600, 20 / 400, 320 / 600, 101 / 400), abs=1e-5)
    assert door.rows[0].box == pytest.approx((20 / 600, 65 / 400, 320 / 600, 77 / 400), abs=1e-5)


def test_narrow_digits_stay_one_word() -> None:
    """'11' and '111': the glyph of 1 is much narrower than its advance, so the gap between the
    inked parts is as wide as a space."""
    door = by_title(tables_of(schedules_pdf()))["DOOR SCHEDULE"]
    assert door.rows[0].cells[1] == "11"
    assert door.rows[2].cells[0] == "111"


def test_stacked_boxes_on_the_same_columns_are_one_schedule() -> None:
    keys = by_title(tables_of(schedules_pdf()))["KEYNOTES"]
    assert keys.columns == ("Category", "Key", "Note")
    assert [row.cells for row in keys.rows] == [
        ("DOOR", "GL-1", "GLASS"),
        ("DOOR", "WD-1", "SOLID CORE"),
        ("FRAME", "AL-1", "ALUMINIUM"),
    ]
    assert keys.key_column == 1  # column 0 repeats, the keys do not
    assert keys.box == pytest.approx((350 / 600, 20 / 400, 560 / 600, 106 / 400), abs=1e-5)


def test_boxes_without_a_title_row_are_no_schedule() -> None:
    assert sorted(t.title or "" for t in tables_of(schedules_pdf())) == [
        "DOOR SCHEDULE",
        "KEYNOTES",
    ]


def test_a_text_matrix_that_scales_the_font_still_gives_words_and_lines() -> None:
    """pdfium's font size leaves out the text matrix: text set at 100 pt and scaled to 6 pt must
    be measured by its drawn height, or words lose their spaces and lines run together."""
    sheet = SheetPdf()
    door_schedule(sheet)
    scaled_text(sheet, "Fire Rating", DOOR_XS[0] + 2, 230)
    scaled_text(sheet, "Two Words", DOOR_XS[0] + 2, 238)
    ruled(sheet, (20.0, 80.0, 140.0), (190.0, 205.0, 220.0, 241.0), no_down=frozenset({(0, 1)}))
    put(sheet, "SCALED", 30, 205)
    put(sheet, "Kind", 20, 220)
    put(sheet, "Value", 80, 220)
    put(sheet, "x", 80, 241)
    scaled = by_title(tables_of(sheet.pdf()))["SCALED"]
    assert scaled.rows[0].cells == ("Fire Rating Two Words", "x")


def scaled_text(sheet: SheetPdf, text: str, x: float, y: float) -> None:
    document, page = sheet._document, sheet._page  # pyright: ignore[reportPrivateUsage]
    obj = raw.FPDFPageObj_NewTextObj(document.raw, b"Helvetica", 100.0)
    encoded = (text + "\x00").encode("utf-16-le")
    buffer = ctypes.create_string_buffer(encoded, len(encoded))
    raw.FPDFText_SetText(obj, ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ushort)))
    raw.FPDFPageObj_Transform(obj, 0.06, 0, 0, 0.06, x, sheet.height - y)
    raw.FPDFPage_InsertObject(page.raw, obj)


# --------------------------------------------------------------------------- the decorator


class Files:
    def __init__(self, content: dict[str, bytes]) -> None:
        self.content = content
        self.reads: list[str] = []

    def read(self, path: str) -> bytes:
        self.reads.append(path)
        return self.content[path]


class Inner:
    """The route's own reader: one element and a note."""

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        return Extracted(
            method="parser",
            scale=Scale(status="no_scale"),
            elements=(Element(id="e1", class_="door", page=1, box=(0.1, 0.1, 0.2, 0.2)),),
            notes=("inner",),
        )


def source_and_sheet(pdf: bytes, page: Page | None = None) -> tuple[DrawingFile, Sheet]:
    source = DrawingFile(path="data/demo/A-801.pdf", size=len(pdf), sha256="0" * 64, kind="pdf")
    if page is None:
        return source, Sheet(file=source, pages=(Page(page=1, width=600, height=400, unit="pt"),))
    other = source.model_copy(update={"path": "data/demo/A-801.png", "kind": "png"})
    return source, Sheet(file=other, pages=(page,))


def test_the_tables_join_what_the_inner_reader_found() -> None:
    pdf = schedules_pdf()
    source, sheet = source_and_sheet(pdf)
    got = PdfTables(Inner(), Files({source.path: pdf})).extract(source, sheet)
    assert [element.id for element in got.elements] == ["e1"]
    assert got.tables is not None
    assert [table.title for table in got.tables] == ["DOOR SCHEDULE", "KEYNOTES"]
    assert [table.id for table in got.tables] == ["t1", "t2"]
    assert got.notes == ("inner", "pdf tables: 2 schedules read (DOOR SCHEDULE, KEYNOTES)")


def test_the_render_of_the_sheet_gets_the_same_fractions() -> None:
    pdf = schedules_pdf()
    source, sheet = source_and_sheet(pdf, Page(page=1, width=1200, height=800, unit="px"))
    got = PdfTables(Inner(), Files({source.path: pdf})).extract(source, sheet)
    assert got.tables is not None
    assert got.tables[0].box == pytest.approx((20 / 600, 20 / 400, 320 / 600, 101 / 400), abs=1e-5)


def test_a_sheet_without_a_schedule_keeps_the_inner_result() -> None:
    sheet_pdf = SheetPdf()
    untitled_boxes(sheet_pdf)
    pdf = sheet_pdf.pdf()
    source, sheet = source_and_sheet(pdf)
    got = PdfTables(Inner(), Files({source.path: pdf})).extract(source, sheet)
    assert got == Inner().extract(source, sheet)
    assert got.tables is None


def test_a_sheet_of_another_shape_or_kind_is_not_read() -> None:
    pdf = schedules_pdf()
    source, sheet = source_and_sheet(pdf, Page(page=1, width=800, height=800, unit="px"))
    files = Files({source.path: pdf})
    assert PdfTables(Inner(), files).extract(source, sheet).tables is None
    png = source.model_copy(update={"kind": "png"})
    files.reads.clear()
    assert PdfTables(Inner(), files).extract(png, sheet).tables is None
    assert files.reads == []


def test_tables_are_read_by_default_and_off_leaves_the_vector_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # so a developer's backend/.env can't change the result
    wrapped = build_pipeline(Settings(), tmp_path).extractors["vector"]
    assert isinstance(wrapped, PdfTables)
    assert isinstance(wrapped._inner, PdfVectorExtractor)  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setenv("TABLES", "off")
    assert isinstance(build_pipeline(Settings(), tmp_path).extractors["vector"], PdfVectorExtractor)
