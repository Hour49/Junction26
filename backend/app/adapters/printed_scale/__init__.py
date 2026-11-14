"""`RASTER_PRINTED_SCALE`: a raster sheet's printed scale and printed counts, read by a
`PrintedReader`, replace its estimated scale and check its counts (app/core/pipeline/printed.py).

`PrintedScale(inner, reader, files)` wraps the raster `Extractor` outside `PriorScale`, so the
door estimate is made first and kept as the second value of a `scale` conflict. The image's
resolution, which turns a printed ratio into metres per pixel, is what the file itself states
(PNG pHYs, JPEG density), trusted only as `printed.trusted_dpi` says.

The reader is the Carbon reader's `printed_scale` and `printed_facts` plus the scale bar's ends on
a full-resolution tile (`carbon`); that client is not in this build yet, so `carbon` is refused
at startup and tests use a fake reader.
"""

import io

from PIL import Image

from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import DrawingFiles, Extractor, PrintedReader
from app.core.pipeline.printed import trusted_dpi, with_printed


class PrintedScale:
    def __init__(self, inner: Extractor, reader: PrintedReader, files: DrawingFiles) -> None:
        self._inner = inner
        self._reader = reader
        self._files = files

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        found = self._inner.extract(source, sheet)
        if not sheet.pages:
            return found
        dpi = trusted_dpi(stated_dpi(self._files.read(source.path)))
        return with_printed(found, self._reader.read(source, sheet), sheet.pages, dpi)


def stated_dpi(data: bytes) -> tuple[float, float] | None:
    """The resolution the image file states, or None (no image, or none stated)."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            dpi = image.info.get("dpi")
    except (OSError, ValueError, Image.DecompressionBombError):
        return None
    if not isinstance(dpi, tuple) or len(dpi) != 2:
        return None
    x, y = (float(value) for value in dpi)
    return x, y
