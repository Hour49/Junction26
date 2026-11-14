"""A big greyscale page is held once in its own mode: no full-page RGB copy at any reader, and
every reader's bytes (hashes, JPEGs, model inputs) are the ones the full copy gave.

The memory check is deterministic: it records the size of every image `convert` is called on."""

import hashlib
import io

import numpy as np
import pytest
from PIL import Image

from app.adapters.carbon import contract
from app.adapters.carbon import reader as carbon_reader
from app.adapters.count_arbiter import L1PageCounts
from app.adapters.raster_detector import post
from app.adapters.raster_ocr import gemini

BIG = 100  # px: "full page" for these tests is anything wider than a digest strip or a 1024 canvas


def noise(mode: str, width: int, height: int) -> Image.Image:
    rng = np.random.default_rng(7)
    shape = (height, width) if mode == "L" else (height, width, len(mode))
    return Image.fromarray(rng.integers(0, 256, shape, dtype=np.uint8), mode)


@pytest.fixture
def converted(monkeypatch):
    """Pixel counts of the images `convert` was called on (and the mode asked for)."""
    calls: list[tuple[int, str]] = []
    original = Image.Image.convert

    def spy(self, mode=None, *args, **kwargs):
        calls.append((self.width * self.height, mode))
        return original(self, mode, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "convert", spy)
    return calls


def old_digest(image: Image.Image) -> str:
    rgb = image.convert("RGB")
    return hashlib.sha256(f"{rgb.width}x{rgb.height}:".encode() + rgb.tobytes()).hexdigest()


@pytest.mark.parametrize("mode", ["L", "RGB", "RGBA"])
def test_digest_is_the_full_copy_hash(mode):
    image = noise(mode, 130, gemini.DIGEST_ROWS * 2 + 37)  # three strips, the last one short
    assert gemini.pixel_digest(image) == old_digest(image)


def test_digest_converts_a_strip_at_a_time(converted):
    image = noise("L", 130, gemini.DIGEST_ROWS * 3)
    gemini.pixel_digest(image)
    assert converted and max(pixels for pixels, _ in converted) <= 130 * gemini.DIGEST_ROWS


def old_jpeg(image: Image.Image) -> bytes:
    rgb = image.convert("RGB")
    size = contract.sent_size(*rgb.size)
    if size != rgb.size:
        rgb = rgb.resize(size, Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    rgb.save(buffer, format="JPEG", quality=contract.JPEG_QUALITY)
    return buffer.getvalue()


@pytest.mark.parametrize("mode", ["L", "RGB"])
def test_jpeg_bytes_are_unchanged(mode):
    image = noise(mode, contract.MAX_SIDE + 300, 400)  # wider than the sent size: resized
    assert carbon_reader.jpeg(image) == old_jpeg(image)


def test_jpeg_of_a_grey_page_resizes_before_converting(converted):
    image = noise("L", contract.MAX_SIDE + 300, 400)
    carbon_reader.jpeg(image)
    assert max(pixels for pixels, _ in converted) < image.width * image.height


def test_carbon_holds_the_page_in_its_own_mode(monkeypatch):
    seen: list[str] = []

    def stop(self, kind, image):
        seen.append(image.mode)
        raise RuntimeError("stop")

    monkeypatch.setattr(carbon_reader.CarbonReader, "_ask", stop)
    with pytest.raises(RuntimeError):
        carbon_reader.CarbonReader(None, None).read(noise("L", 64, 48))  # type: ignore[arg-type]
    assert set(seen) == {"L"}


def canvas_bytes(image: Image.Image, side: int) -> bytes:
    canvas, _ = post.letterbox(image, side)
    return canvas.tobytes()


@pytest.mark.parametrize("mode", ["L", "RGB", "P", "LA"])
def test_open_page_gives_the_same_canvas_as_open_rgb(mode):
    image = noise(mode if mode != "P" else "L", 300, 200)
    if mode == "P":
        image = image.convert("P")
    assert canvas_bytes(post.open_page(image), 64) == canvas_bytes(post.open_rgb(image), 64)


def test_open_page_keeps_a_grey_page_grey_and_converts_the_rest(converted):
    grey = noise("L", BIG, BIG)
    assert post.open_page(grey).mode == "L"
    assert not converted
    assert post.open_page(noise("RGBA", 8, 8)).mode == "RGB"


def test_detector_canvas_for_a_tile_of_a_grey_page(converted):
    page = post.open_page(noise("L", 500, 400))
    post.letterbox(page.crop((0, 0, 300, 300)), 64)
    assert max(pixels for pixels, _ in converted) <= 64 * 64


def test_l1_input_is_the_same_and_a_grey_page_is_not_copied(converted):
    buffer = io.BytesIO()
    noise("L", 400, 300).save(buffer, format="PNG")
    counts = object.__new__(L1PageCounts)
    counts._size = 64
    got = counts.page(buffer.getvalue())
    assert not [c for c in converted if c[0] >= 400 * 300]
    with Image.open(io.BytesIO(buffer.getvalue())) as image:
        gray = image.convert("L").resize((64, 48), Image.Resampling.LANCZOS)
    canvas = Image.new("L", (64, 64), 255)
    canvas.paste(gray, (0, 0))
    assert np.array_equal(got, (np.asarray(canvas, np.float32) / 255.0)[None, None])
