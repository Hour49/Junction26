"""Room labels of CubiCasa raster plans by OCR: a component for the raster route.

- `RoomLabelReader(engine).read(PIL image) -> RoomLabels(rooms, notes)`: one `Room` per printed
  label the room label table knows (reader.py; table in room_labels.json, rebuilt by
  build_room_labels.py from dev gold only).
- `RapidOcrEngine()` is the engine (engine.py); tests give the reader a fake one.
- `OcrRoomExtractor(files)` is the same reader behind the `Extractor` port, for the raster route
  as a whole or for a composing extractor (integ wires it; no setting names it here). Its
  `read` is ("room",): it looks for rooms only, so element counts stay unknown, not 0.

- `GeminiRoomExtractor(files, GeminiRoomReader(GeminiClient(key, model, timeout_s), cache_dir))`
  (gemini.py, arm G4) reads the rooms with Gemini instead, the better reader on val; settings
  GEMINI_*, wired by integ. A failed call leaves the rooms unread, with the reason in the notes.

Positions are fractions of the page; the scale is not read (`no_scale`).
"""

import io

from PIL import Image

from app.adapters.raster_ocr.engine import RapidOcrEngine
from app.adapters.raster_ocr.gemini import (
    GeminiClient,
    GeminiError,
    GeminiRoomExtractor,
    GeminiRoomReader,
)
from app.adapters.raster_ocr.reader import RoomLabelReader, RoomLabels, TextEngine
from app.core.drawing.model import Scale
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import DrawingFiles

__all__ = [
    "GeminiClient",
    "GeminiError",
    "GeminiRoomExtractor",
    "GeminiRoomReader",
    "OcrRoomExtractor",
    "RapidOcrEngine",
    "RoomLabelReader",
    "RoomLabels",
    "TextEngine",
]


class OcrRoomExtractor:
    def __init__(self, files: DrawingFiles, engine: TextEngine | None = None) -> None:
        self._files = files
        self._reader = RoomLabelReader(engine or RapidOcrEngine())

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        with Image.open(io.BytesIO(self._files.read(source.path))) as image:
            found = self._reader.read(image)
        return Extracted(
            method="printed_label",
            scale=Scale(status="no_scale"),
            rooms=found.rooms,
            read=("room",),
            notes=found.notes,
        )
