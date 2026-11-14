"""TIFF and WebP uploads are unpacked as 8-bit PNG sheets, one per TIFF page."""

import io

import numpy as np
import pytest
from PIL import Image

from app.adapters.archive import ZipUnpacker, raster
from app.core.ingest.model import Entry
from app.core.pipeline.identify import sniff


def encode(image: Image.Image, fmt: str, **options: object) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, fmt, **options)
    return buffer.getvalue()


def plan(mode: str = "L", size: tuple[int, int] = (120, 80)) -> Image.Image:
    grey = Image.new("L", size, 255)
    grey.paste(0, (10, 10, size[0] - 10, 14))
    return grey.convert(mode)


def unpack(name: str, data: bytes) -> dict[str, Entry]:
    return {entry.path: entry for entry in ZipUnpacker().entries(name, data)}


def decoded(entry: Entry) -> Image.Image:
    assert entry.data is not None and sniff(entry.data) == "png"
    return Image.open(io.BytesIO(entry.data))


def test_group4_tiff_becomes_an_8bit_png_with_the_drawing_kept() -> None:
    data = encode(plan("1"), "TIFF", compression="group4")
    entries = unpack("scan.tif", data)
    assert list(entries) == ["scan.png"]
    image = decoded(entries["scan.png"])
    assert image.mode == "L" and image.size == (120, 80)
    assert np.asarray(image)[12, 60] == 0 and np.asarray(image)[40, 60] == 255


def test_each_page_of_a_multipage_tiff_is_a_sheet() -> None:
    first, second = plan(), plan(size=(60, 40))
    data = encode(first, "TIFF", save_all=True, append_images=[second], compression="tiff_lzw")
    entries = unpack("set.tiff", data)
    assert list(entries) == ["set.png", "set#p2.png"]
    assert decoded(entries["set#p2.png"]).size == (60, 40)


def test_lzw_rgb_tiff() -> None:
    entries = unpack("c.tif", encode(plan("RGB"), "TIFF", compression="tiff_lzw"))
    assert decoded(entries["c.png"]).mode == "RGB"


def test_webp() -> None:
    entries = unpack("p.webp", encode(plan("RGB"), "WEBP", lossless=True))
    image = decoded(entries["p.png"])
    assert image.size == (120, 80) and image.mode == "RGB"


def test_16bit_tiff_is_scaled_not_clipped() -> None:
    grey = np.full((40, 60), 40000, np.uint16)  # light grey: clipping would turn it white
    data = encode(Image.frombytes("I;16", (60, 40), grey.tobytes()), "TIFF")
    image = decoded(unpack("deep.tif", data)["deep.png"])
    assert image.mode == "L" and np.asarray(image)[5, 5] == 40000 >> 8


def test_exif_orientation_is_applied() -> None:
    image = plan("RGB")
    exif = Image.Exif()
    exif[0x0112] = 6  # rotated a quarter turn
    data = encode(image, "WEBP", lossless=True, exif=exif)
    assert decoded(unpack("r.webp", data)["r.png"]).size == (80, 120)


def test_tiff_inside_a_zip_keeps_its_folder() -> None:
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("floors/a.tif", encode(plan("1"), "TIFF", compression="group4"))
    assert list(unpack("u.zip", buffer.getvalue())) == ["floors/a.png"]


def test_a_broken_tiff_is_set_aside_with_a_reason() -> None:
    entry = unpack("bad.tif", b"II*\x00" + b"\x00" * 16)["bad.tif"]
    assert entry.data is None and "cannot be read" in (entry.refused or "")


def test_pages_past_the_cap_are_named(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(raster, "MAX_PAGES", 2)
    pages = [plan(size=(30, 20))] * 3
    data = encode(pages[0], "TIFF", save_all=True, append_images=pages[1:])
    entries = unpack("many.tif", data)
    assert list(entries) == ["many.png", "many#p2.png", "many#p3.png"]
    assert "pages after 2" in (entries["many#p3.png"].refused or "")


def test_an_image_over_the_pixel_cap_is_set_aside(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(raster, "MAX_PIXELS", 1000)
    entry = unpack("big.tif", encode(plan("1"), "TIFF", compression="group4"))["big.png"]
    assert entry.data is None and "cap" in (entry.refused or "")


def test_png_and_pdf_pass_through() -> None:
    png = encode(plan(), "PNG")
    assert unpack("a.png", png)["a.png"].data == png
