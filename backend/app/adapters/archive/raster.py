"""TIFF and WebP uploads, converted once at unpack to the PNG every raster reader takes.

A scanner's TIFF is often 1-bit CCITT G4 or LZW, sometimes several pages, sometimes 16-bit; a
WebP is lossy or lossless RGB. Neither is read by the rest of the pipeline, so each is written
again as an 8-bit PNG (greyscale when the file is, so no full-page RGB copy of a 1-bit scan) with
EXIF orientation applied, as `ExifFrame` does for PNG and JPEG. Each TIFF page is a sheet of its
own: page 1 at `<name>.png`, page n at `<name>#p<n>.png`. The original bytes are not kept.

Set aside, with the reason: a file Pillow cannot decode, an image over `MAX_PIXELS`, and TIFF
pages after `MAX_PAGES`.
"""

import io
from collections.abc import Iterator
from pathlib import PurePosixPath

from PIL import Image, ImageOps, UnidentifiedImageError

from app.adapters.eight_bit import eight_bit
from app.core.ingest.model import Entry

MAX_PIXELS = 150_000_000  # an 8-bit greyscale page of this size is 150 MB in memory
MAX_PAGES = 50
PNG_LEVEL = 3  # a page of 100 Mpx at the default level 6 takes tens of seconds

_TIFF = (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+")


def raster_format(data: bytes) -> str | None:
    """ "tiff" or "webp" by the file's first bytes, else None."""
    if data.startswith(_TIFF):
        return "tiff"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def converted(entry: Entry) -> Iterator[Entry]:
    """The entry itself, or the PNG entries of the TIFF or WebP it holds."""
    if entry.data is None or raster_format(entry.data) is None:
        yield entry
        return
    path = PurePosixPath(entry.path)
    try:
        image = Image.open(io.BytesIO(entry.data))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        yield Entry(
            path=entry.path, size=entry.size, refused=f"an image that cannot be read: {error}"
        )
        return
    with image:
        count = min(getattr(image, "n_frames", 1), MAX_PAGES)
        for page in range(count):
            yield _page(image, page, _name(path, page + 1), entry.size)
        if getattr(image, "n_frames", 1) > MAX_PAGES:
            why = f"pages after {MAX_PAGES} were not read"
            yield Entry(path=_name(path, MAX_PAGES + 1), size=0, refused=why)


def _name(path: PurePosixPath, number: int) -> str:
    return f"{path.with_suffix('')}.png" if number == 1 else f"{path.with_suffix('')}#p{number}.png"


def _page(image: Image.Image, page: int, path: str, size: int) -> Entry:
    try:
        image.seek(page)
        if image.width * image.height > MAX_PIXELS:
            why = f"a {image.width}x{image.height} image is over the {MAX_PIXELS // 10**6} Mpx cap"
            return Entry(path=path, size=size, refused=why)
        grey = _eight_bit(ImageOps.exif_transpose(image))
        buffer = io.BytesIO()
        grey.save(buffer, "PNG", compress_level=PNG_LEVEL)
    except (OSError, ValueError, SyntaxError, EOFError, Image.DecompressionBombError) as error:
        return Entry(path=path, size=size, refused=f"an image page that cannot be read: {error}")
    return Entry(path=path, size=size, data=buffer.getvalue())


def _eight_bit(image: Image.Image) -> Image.Image:
    if image.mode.startswith("I;16"):
        return eight_bit(image)
    if image.mode == "1":
        return image.convert("L")
    if image.mode in ("L", "LA", "RGB", "RGBA"):
        return image
    return image.convert("RGBA" if "A" in image.mode or "transparency" in image.info else "RGB")
