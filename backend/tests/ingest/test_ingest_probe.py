"""Identify by content: what each kind of file is called, from its bytes alone."""

import io
import zipfile

import pytest
from PIL import Image
from test_vector_pdf import swiss_sheet

from app.adapters.archive import FileProbe
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
