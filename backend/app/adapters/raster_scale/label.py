"""`LABEL_SCALE=on`: a raster sheet's room labels give its scale (app/core/pipeline/label_scale.py).

`LabelScale(inner, kind_of, rectified)` wraps the raster `Extractor` outside `PrintedScale`, so it
sees the sheet's final scale: a measured bar or a trusted printed ratio (`scaled`) stays, the door
estimate or no scale may give way to the label scale. A camera photo (`kind_of`: ingest's content
kind) counts only when the rectifier straightened it (`rectified`: its stored frame says so): in
perspective one scale does not hold across the page. The CLI keeps no frame: its photos are left
as they are.
"""

from collections.abc import Callable

from app.adapters.printed_scale import CAMERA
from app.core.pipeline.label_scale import with_label_scale
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import Extractor


class LabelScale:
    def __init__(
        self,
        inner: Extractor,
        kind_of: Callable[[str], str | None],
        rectified: Callable[[str], bool],
        always: bool = False,
    ) -> None:
        self._inner = inner
        self._kind_of = kind_of
        self._rectified = rectified
        self._always = always  # LABEL_SCALE=always: replace a door estimate inside its band

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        found = self._inner.extract(source, sheet)
        if self._kind_of(source.path) in CAMERA and not self._rectified(source.path):
            return found
        return with_label_scale(found, sheet.pages, self._always)
