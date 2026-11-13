"""What ingest needs from outside, as Protocols. app/adapters implements them, app/composition.py
picks one per port, and the tests pass fakes."""

from collections.abc import Sequence
from typing import Protocol

from app.core.drawing.model import Drawing, Page
from app.core.pipeline.model import DrawingFile, Extracted, Measurement, Sheet


class DrawingFiles(Protocol):
    """File access: the bytes of a file, by the path the dataset (or an upload) gives it."""

    def read(self, path: str) -> bytes: ...


class SourceFinder(Protocol):
    """Stage 4's lookup: the richer sources the store holds for a sheet beyond the files a run
    was given, e.g. the building model a plan sheet was rendered from. They join the sheet's
    group, so stage 5 can route to them. A finder names a source only when the route's extractor
    can read the sheet from it; a sheet without one keeps the route of its own files."""

    def sources(self, path: str) -> Sequence[str]: ...


class PageReader(Protocol):
    """The pages of a sheet file as rendered (after any PDF /Rotate), in order from page 1."""

    def pages(self, file: DrawingFile) -> tuple[Page, ...]: ...


class Extractor(Protocol):
    """One route's reader. It reads `source`, the richest file of the drawing's group, and
    returns what it found as page fractions of `sheet`, which may be another file of the group.
    It also says what it looked for (`read`): a class it leaves out has no count, not a count
    of 0. A room area it gives is the room's outline at the sheet's scale: stage 8 compares it
    with a printed area under that name (`polygon_x_scale`).

    A building model that is asked about itself has no page: the model route's extractor then
    gets it as `source` and as a `sheet` without pages, and gives the model's objects
    (`model_objects`) with nothing placed, or nothing, and the file is set aside."""

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted: ...


class SecondCounter(Protocol):
    """An independent second method: what it measured on the sheet, by another method than the
    extractor's. A quantity it leaves out was not measured a second time. It may give two
    readings of its own for one quantity (the scale as printed and as the bar measures it). A
    room is named by the id the extractor gave it."""

    def measure(self, source: DrawingFile, sheet: Sheet) -> Sequence[Measurement]: ...


class DrawingSink(Protocol):
    """Where a finished drawing model goes."""

    def write(self, drawing: Drawing) -> None: ...
