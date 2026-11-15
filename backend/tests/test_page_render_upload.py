"""render_upload (the preview of an upload as it came): bytes no decoder opens are an
InvalidInputError, not a raw OSError/PdfiumError (R6-c-8)."""

import io

import pytest
from PIL import Image

from app.adapters.page_render import render_upload
from app.core.errors import InvalidInputError
from scripts.make_sample_archive import raster_plan


def jpeg() -> bytes:
    buffer = io.BytesIO()
    raster_plan().convert("RGB").save(buffer, "JPEG")
    return buffer.getvalue()


def test_a_decodable_image_is_rendered() -> None:
    png = render_upload(jpeg(), "jpeg_plan", 400)
    with Image.open(io.BytesIO(png)) as image:
        assert image.width == 400


@pytest.mark.parametrize("kind", ["jpeg_plan", "photo_plan", "png_plan", "photo"])
@pytest.mark.parametrize("damage", ["truncated", "garbled"])
def test_an_image_that_cannot_be_decoded_is_invalid_input(kind: str, damage: str) -> None:
    data = jpeg()
    broken = data[: len(data) // 5] if damage == "truncated" else data[:20] + b"\x00" * 400
    with pytest.raises(InvalidInputError, match="cannot be decoded"):
        render_upload(broken, kind, 400)


def test_a_pdf_that_cannot_be_opened_is_invalid_input() -> None:
    with pytest.raises(InvalidInputError, match="cannot be decoded"):
        render_upload(b"%PDF-1.7\n garbage", "pdf_scan", 400)


def test_an_image_too_large_to_open_has_no_preview_in_plain_words(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """QA R4-G2: Pillow's decompression-bomb text never reaches the screen."""
    data = jpeg()
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 10)
    with pytest.raises(InvalidInputError) as refused:
        render_upload(data, "jpeg_plan", 400)
    assert "an image too large to open safely" in str(refused.value)
    assert "DOS attack" not in str(refused.value)
