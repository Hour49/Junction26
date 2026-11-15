"""`RASTER_PHOTO_COMPONENTS`: camera photos of a plan get their own raster reader.

A detector trained on phone photos reads them better than the scan detector, but loses on clean
scans (photo's PSy-photostyle: hard photos +4.4 pp, clean scans -1.0 pp on val;
.agents/exp/photo.md Run 5). So the raster route asks what ingest identified the file as: a
`photo_plan` (EXIF or the Gemini kind signal) goes to the photo reader, every other raster (a
scanned PDF, a PNG or JPEG plan) to the shipped one.
"""

from collections.abc import Callable

from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import Extractor

PHOTO = "photo_plan"


class PhotoSwitch:
    def __init__(
        self, other: Extractor, photo: Extractor, kind_of: Callable[[str], str | None]
    ) -> None:
        self._other = other
        self._photo = photo
        self._kind_of = kind_of  # the content kind ingest gave a file, by its path

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        reader = self._photo if self._kind_of(source.path) == PHOTO else self._other
        return reader.extract(source, sheet)
