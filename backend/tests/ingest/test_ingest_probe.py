"""Identify by content: what each kind of file is called, from its bytes alone."""

import io
import random
import re
import zipfile

import pypdfium2
import pytest
from PIL import Image, ImageFilter
from pypdfium2 import raw
from test_vector_pdf import swiss_sheet

from app.adapters.archive import FileProbe
from app.adapters.page_render import render_png
from app.core.ingest.model import SheetFile
from scripts.make_sample_archive import (
    ifc_model,
    jpeg_bytes,
    phone_photo,
    png_bytes,
    raster_plan,
    site_photo,
    text_pdf,
)


def kind(data: bytes) -> str:
    return FileProbe().probe(data).kind


def scanned_pdf() -> bytes:
    buffer = io.BytesIO()
    raster_plan().save(buffer, "PDF", resolution=100)
    return buffer.getvalue()


def jpeg(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "JPEG")
    return buffer.getvalue()


def test_pdfs_are_told_apart_by_what_page_one_holds() -> None:
    assert kind(swiss_sheet().pdf()) == "pdf_vector"
    assert kind(scanned_pdf()) == "pdf_scan"
    assert kind(text_pdf()) == "pdf_text"
    assert FileProbe().probe(scanned_pdf()).did.startswith("a scanned PDF, images cover 100%")


def test_images_drawings_and_photos() -> None:
    plan = raster_plan()
    assert kind(png_bytes(plan)) == "png_plan"
    assert kind(jpeg(plan)) == "jpeg_plan"
    assert kind(jpeg_bytes(phone_photo(plan))) == "photo_plan"  # camera EXIF, paper with ink
    assert kind(jpeg_bytes(site_photo())) == "photo"  # camera EXIF, no paper
    # without camera EXIF nothing is called a photo: setting a file aside needs evidence
    assert kind(jpeg(site_photo())) == "jpeg_plan"
    assert kind(png_bytes(Image.new("RGB", (40, 300), "white"))) == "unknown"  # too small to read


def noise(width: int, height: int) -> Image.Image:
    """Random grey pixels, seeded: an image with no structure at all."""
    return Image.frombytes("L", (width, height), random.Random(0).randbytes(width * height))


def test_images_with_no_drawing_in_them_are_set_aside_as_not_drawings() -> None:
    # QA R2-qa5-1: these were "ready" plans whose questions answered a measured 0
    size = (1600, 1200)
    for image in (
        Image.new("RGB", size, "black"),
        Image.new("RGB", size, "white"),
        noise(*size).convert("RGB"),
        raster_plan().filter(ImageFilter.GaussianBlur(25)),  # a plan blurred past reading
    ):
        probed = FileProbe().probe(jpeg(image))
        assert probed.kind == "unknown", probed.did
        assert probed.did.startswith("not a drawing: "), probed.did
    # the same plan a little soft is still a drawing, and so is a camera photo of it
    assert kind(jpeg(raster_plan().filter(ImageFilter.GaussianBlur(2)))) == "jpeg_plan"
    assert kind(jpeg_bytes(phone_photo(raster_plan()))) == "photo_plan"


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"", "unknown"),
        (b"Room schedule\nKitchen;12.5\n", "text"),
        (b"AC1032\x00\x00binary", "dwg"),
        (b"0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n", "dxf"),
        (b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"/>', "svg"),
        (b"ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('AP214'));", "unknown"),  # STEP, not IFC
        (b"\x00\x01\x02\x03" * 100, "unknown"),
        (b"%PDF-1.7 broken", "unknown"),
    ],
)
def test_other_files(data: bytes, expected: str) -> None:
    assert kind(data) == expected


def test_an_ifc_model() -> None:
    assert kind(ifc_model()) == "ifc"


def test_a_zip_that_reaches_the_probe_is_named() -> None:
    def zipped(name: str) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(name, b"<x/>")
        return buffer.getvalue()

    assert kind(zipped("[Content_Types].xml")) == "office"
    assert kind(zipped("plan.pdf")) == "archive"


# Real PDFs ingest set aside or half-read (2026-11-14, .agents/briefs/ingest-setaside-bugs.md). The
# fixtures are built here: no dataset file is in the repo.


def _saved(document: pypdfium2.PdfDocument) -> bytes:
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def ink_sketch_pdf(markup_on: bytes | None = None) -> bytes:
    """A plan sketched by hand as one Ink annotation (a pen on a tablet), on an empty page or
    as a markup on `markup_on`'s page 1."""
    document = pypdfium2.PdfDocument(markup_on) if markup_on else pypdfium2.PdfDocument.new()
    page = document[0] if markup_on else document.new_page(612, 792)
    annot = raw.FPDFPage_CreateAnnot(page.raw, raw.FPDF_ANNOT_INK)
    raw.FPDFAnnot_SetColor(annot, raw.FPDFANNOT_COLORTYPE_Color, 200, 0, 0, 255)
    raw.FPDFAnnot_SetRect(annot, raw.FS_RECTF(100, 700, 500, 100))
    walls = [(100, 100, 500, 100), (500, 100, 500, 700), (500, 700, 100, 700), (100, 700, 100, 100)]
    for x0, y0, x1, y1 in [*walls, (300, 100, 300, 700)]:
        points = (raw.FS_POINTF * 2)(raw.FS_POINTF(x0, y0), raw.FS_POINTF(x1, y1))
        raw.FPDFAnnot_AddInkStroke(annot, points, 2)
    raw.FPDFPage_CloseAnnot(annot)
    return _saved(document)


def stamped_plan_pdf() -> bytes:
    """A drawing pasted as a Stamp annotation: its paths live in the stamp's appearance, the
    page itself holds nothing."""
    document = pypdfium2.PdfDocument.new()
    page = document.new_page(800, 400)
    annot = raw.FPDFPage_CreateAnnot(page.raw, raw.FPDF_ANNOT_STAMP)
    raw.FPDFAnnot_SetRect(annot, raw.FS_RECTF(50, 350, 750, 50))
    for index in range(12):
        wall = raw.FPDFPageObj_CreateNewRect(60 + 55 * index, 60, 50, 280)
        raw.FPDFPageObj_SetStrokeColor(wall, 0, 0, 0, 255)
        raw.FPDFPath_SetDrawMode(wall, raw.FPDF_FILLMODE_NONE, True)
        raw.FPDFAnnot_AppendObject(annot, wall)
    raw.FPDFPage_CloseAnnot(annot)
    return _saved(document)


def drawing_set_pdf() -> bytes:
    """A permit set: page 1 is the notes sheet (text), page 2 a drawn plan."""
    document = pypdfium2.PdfDocument(text_pdf())
    document.import_pages(pypdfium2.PdfDocument(swiss_sheet().pdf()))
    return _saved(document)


def misplaced_page_pdf() -> bytes:
    """A PDF whose cross-reference table points page 1's object at the wrong bytes (an editor
    shifted the objects and kept the old offsets): the file opens, its page does not load."""
    data = swiss_sheet().pdf()
    page = re.search(rb"(\d+) 0 obj\s*<<(?:(?!endobj).)*?/Type\s*/Page(?!s)", data, re.DOTALL)
    table = re.search(rb"xref\s+(\d+) \d+\s+", data)
    assert page is not None and table is not None, "the fixture expects one classic xref table"
    number, at = int(page.group(1)), page.start()
    entry = table.end() + 20 * (number - int(table.group(1)))  # entries are 20 bytes each
    assert int(data[entry : entry + 10]) == at
    return data[:entry] + b"%010d" % (at + 7) + data[entry + 10 :]


def test_a_drawing_held_only_in_annotations_is_read_as_an_image() -> None:
    for data, held in ((ink_sketch_pdf(), "1 ink drawing"), (stamped_plan_pdf(), "1 stamp")):
        found = FileProbe().probe(data)
        assert found.kind == "pdf_scan", found.did
        assert found.did.startswith(f"a drawing held in the PDF's annotations ({held}"), found.did


def test_markups_on_a_drawn_page_leave_it_a_drawn_pdf() -> None:
    assert kind(ink_sketch_pdf(markup_on=swiss_sheet().pdf())) == "pdf_vector"


def test_annotations_are_drawn_when_a_page_is_rendered() -> None:
    sheet = SheetFile(drawing_id="d", path="sketch.pdf", kind="pdf", data=ink_sketch_pdf())
    with Image.open(io.BytesIO(render_png(sheet, 1, 400))) as image:
        darkest, _ = image.convert("L").getextrema()
    assert isinstance(darkest, int) and darkest < 128  # the red strokes, on white paper


def test_a_set_whose_first_page_is_text_names_its_drawn_pages() -> None:
    found = FileProbe().probe(drawing_set_pdf())
    assert found.kind == "pdf_text"  # the vector reader reads page 1 only (vector_pdf)
    assert found.did.endswith("; page 2 holds a drawing, which is not read (only page 1 is)")


def test_a_pdf_whose_page_does_not_load_is_named_damaged() -> None:
    found = FileProbe().probe(misplaced_page_pdf())
    assert found.kind == "unknown"
    assert found.did.startswith("a damaged PDF: page 1 does not load"), found.did
