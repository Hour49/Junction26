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
import re
from collections.abc import Iterator
from pathlib import PurePosixPath

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.adapters.eight_bit import eight_bit
from app.core.ingest.model import Entry
from app.core.pipeline.identify import sniff_raster

MAX_PIXELS = 150_000_000  # 8-bit grey: 150 MB; RGB: 450 MB; the conversion holds a copy more
MAX_PAGES = 50
ORIENTATION = 0x0112
PNG_LEVEL = 3  # a page of 100 Mpx at the default level 6 takes tens of seconds


def too_large(error: Image.DecompressionBombError) -> str:
    """Why Pillow refused to open an image (its decompression-bomb guard), in plain words: never
    Pillow's own text. The size is read from that text, so it is left out if Pillow rewords it."""
    found = re.search(r"\((\d+) pixels\)", str(error))
    size = f"{round(int(found[1]) / 1e6)} megapixels; " if found else ""
    limit = 2 * (Image.MAX_IMAGE_PIXELS or 0)  # Pillow refuses over twice its warning size
    return f"an image too large to open safely ({size}the limit is {round(limit / 1e6)})"


def converted(entry: Entry) -> Iterator[Entry]:
    """The entry itself, or the PNG entries of the TIFF or WebP it holds."""
    if entry.data is None or sniff_raster(entry.data) is None:
        yield entry
        return
    path = PurePosixPath(entry.path)
    try:
        image = Image.open(io.BytesIO(entry.data))
    except Image.DecompressionBombError as error:
        yield Entry(path=entry.path, size=entry.size, refused=too_large(error))
        return
    except (UnidentifiedImageError, OSError) as error:
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
        turned = image.getexif().get(ORIENTATION) not in (None, 1)
        grey = _eight_bit(ImageOps.exif_transpose(image) if turned else image)
        buffer = io.BytesIO()
        grey.save(buffer, "PNG", compress_level=PNG_LEVEL)
    except Image.DecompressionBombError as error:
        return Entry(path=path, size=size, refused=too_large(error))
    except (OSError, ValueError, SyntaxError, EOFError) as error:
        return Entry(path=path, size=size, refused=f"an image page that cannot be read: {error}")
    return Entry(path=path, size=size, data=buffer.getvalue())


def _eight_bit(image: Image.Image) -> Image.Image:
    if image.mode.startswith("I;16"):
        return eight_bit(image)
    if image.mode == "1":
        return image.convert("L")
    if image.mode in ("L", "LA", "RGB", "RGBA"):
        return image
    if image.mode in ("I", "F"):  # 32-bit integers and floats: scaled to their own range
        return _scaled(image)
    if image.mode == "P" and "transparency" not in image.info and _grey_palette(image):
        return image.convert("L")
    return image.convert("RGBA" if "A" in image.mode or "transparency" in image.info else "RGB")


def _grey_palette(image: Image.Image) -> bool:
    palette = image.getpalette()
    if palette is None:
        return False
    return palette[0::3] == palette[1::3] == palette[2::3]


def _scaled(image: Image.Image) -> Image.Image:
    """A 32-bit integer or float page as 8-bit grey, its lowest value black and its highest
    white (`convert` would clip an integer page and turn a 0..1 float page into 0 and 1)."""
    values = np.nan_to_num(np.asarray(image, np.float32))
    low, high = float(values.min()), float(values.max())
    if high <= low:
        return Image.new("L", image.size, 0)
    return Image.fromarray(((values - low) * (255.0 / (high - low))).astype(np.uint8), "L")
