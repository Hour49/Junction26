"""The local raster reading (the detectors, the arbiter, the region and room readers of the
composite) one sheet at a time in this process.

Ingest reads several drawing groups at once (INGEST_GROUPS_IN_FLIGHT) so that their Carbon calls,
which mostly wait on the network, overlap. The local reading of a big sheet holds gigabytes (eight
views of a 138-megapixel page): four of them side by side went past the backend's memory and
swapped (codecheck, 2026-11-15: a 6-image upload 37 s -> 288 s on cached replies). Held only around
the local reader, this lock keeps one such reading in memory at a time while the Carbon calls the
reader is wrapped in (CarbonThings, CarbonChecked, PrintedScale run them beside it) go on."""

import threading

from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import Extractor

_one = threading.Lock()


class OneAtATime:
    def __init__(self, inner: Extractor) -> None:
        self._inner = inner

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        with _one:
            return self._inner.extract(source, sheet)
