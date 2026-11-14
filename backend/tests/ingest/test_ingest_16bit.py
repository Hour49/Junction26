"""16-bit greyscale PNGs (Pillow mode I;16), such as a scanner writes: Pillow's convert clips every
value above 255 to white instead of scaling it, so a plan with grey lines turned blank and was set
aside (QA r7, review-202 finding 4). Each reader of the upload's own bytes, and the frame that every
later reader and the API see, must read it as the same picture as its 8-bit copy."""

import io
import struct
import zipfile
import zlib

import numpy as np
from conftest import MakeService
from PIL import Image

from app.adapters.archive import ExifFrame, FileProbe
from app.adapters.decisions_kind import page_png
from app.adapters.triage.gemini_describer import encode
from scripts.make_sample_archive import png_bytes, raster_plan


def zipped(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def grey_plan() -> Image.Image:
    """The sample plan as a scan gives it: dark grey lines (40) on white paper, 8-bit."""
    return raster_plan().convert("L").point([40 + v * 215 // 255 for v in range(256)])


def sixteen(image: Image.Image) -> bytes:
    """The same pixels as a 16-bit greyscale PNG (v * 257: 255 -> 65535)."""
    deep = Image.fromarray(np.asarray(image, np.uint16) * 257)
    assert deep.mode == "I;16"
    return png_bytes(deep)


def sixteen_rgb(image: Image.Image) -> bytes:
    """The same pixels as a 16-bit RGB PNG, written by hand (Pillow cannot save one)."""
    rgb = np.repeat(np.asarray(image, np.uint16)[..., None] * 257, 3, axis=2)
    height, width = rgb.shape[:2]
    rows = b"".join(b"\0" + rgb[y].astype(">u2").tobytes() for y in range(height))

    def chunk(tag: bytes, body: bytes) -> bytes:
        crc = struct.pack(">I", zlib.crc32(tag + body))
        return struct.pack(">I", len(body)) + tag + body + crc

    header = struct.pack(">IIBBBBB", width, height, 16, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def test_the_probe_reads_a_16_bit_grey_plan_as_its_8_bit_copy() -> None:
    plan = grey_plan()
    eight = FileProbe().probe(png_bytes(plan))
    assert eight.kind == "png_plan"
    assert FileProbe().probe(sixteen(plan)) == eight


def test_a_16_bit_rgb_plan_is_a_plan() -> None:
    """Pillow scales 16-bit RGB to 8-bit itself (mode RGB): a guard, not the bug."""
    data = sixteen_rgb(grey_plan())
    with Image.open(io.BytesIO(data)) as image:
        assert image.mode == "RGB"
    assert FileProbe().probe(data).kind == "png_plan"


def test_the_frame_writes_a_16_bit_grey_png_as_its_8_bit_copy() -> None:
    plan = grey_plan()
    found = ExifFrame().normalise(sixteen(plan))
    assert found is not None
    data, normalised = found
    with Image.open(io.BytesIO(data)) as image:
        assert (image.format, image.mode) == ("PNG", "L")
        assert np.array_equal(np.asarray(image), np.asarray(plan))
    assert (normalised.exif, normalised.width, normalised.height) == (None, *plan.size)
    eight = png_bytes(plan)
    assert ExifFrame().normalise(eight) == (eight, normalised)  # 8-bit keeps its bytes


def test_the_kind_signal_and_the_describer_send_the_8_bit_picture() -> None:
    plan = grey_plan()
    assert page_png(sixteen(plan)) == page_png(png_bytes(plan))
    assert encode(sixteen(plan)) == encode(png_bytes(plan))


def test_a_16_bit_grey_plan_is_read_not_set_aside_as_blank(make_service: MakeService) -> None:
    """Ends where its 8-bit copy ends (the test reader flags it), not set aside as `unknown`."""
    ingest = make_service()
    plan = grey_plan()
    (eight,) = ingest.status(ingest.start("a.zip", zipped({"scan.png": png_bytes(plan)}))).files
    (found,) = ingest.status(ingest.start("b.zip", zipped({"scan.png": sixteen(plan)}))).files
    assert found.kind == "png_plan" and found.drawing_id is not None
    assert (found.stage, found.state) == (eight.stage, eight.state) != ("route", "set_aside")
