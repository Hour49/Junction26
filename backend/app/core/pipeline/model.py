"""What the ingest stages hand to each other, and the report of a run."""

from typing import Literal

from pydantic import Field

from app.core.drawing.model import (
    Apartment,
    ConflictQuantity,
    Element,
    Mark,
    MeasuredValue,
    MeasureMethod,
    ModelObject,
    Page,
    Plan,
    ReadClass,
    Resolution,
    Room,
    Scale,
    Subject,
    Table,
)
from app.core.model import Frozen

FileKind = Literal["pdf", "png", "jpeg", "svg", "dxf", "ifc"]
Route = Literal["bim", "cad", "vector", "raster"]

# The kinds that have pages, so a drawing model can be written for them (extraction_v1 places
# everything on a page). An IFC model or a DXF is a source to read from, never a sheet.
SHEET_KINDS: frozenset[FileKind] = frozenset({"pdf", "png", "jpeg"})


class FileEntry(Frozen):
    """Stages 1-2: one file of the inventory."""

    path: str  # as the dataset's questions.jsonl gives it: data/<source>/<name>
    size: int
    sha256: str


class DrawingFile(Frozen):
    """Stage 3: an inventory entry whose content is a drawing format."""

    path: str
    size: int
    sha256: str
    kind: FileKind


class SetAside(Frozen):
    """A file the pipeline does not ingest, and why."""

    path: str
    reason: str


class DrawingGroup(Frozen):
    """Stage 4: the files of one drawing (the same plan as PDF, PNG, DXF...)."""

    key: str
    files: tuple[DrawingFile, ...]


class Routed(Frozen):
    """Stage 5: the richest source of a group, and the route that reads it."""

    route: Route
    source: DrawingFile


class Sheet(Frozen):
    """Stage 6: a file with pages, in the frame every position on it is given in."""

    file: DrawingFile
    pages: tuple[Page, ...]


class Extracted(Frozen):
    """Stage 7: what an extractor read, placed on the sheet as page fractions. `method` is how it
    reads, as a conflict names it (`parser`, `detector`, `ifc_model`...)."""

    method: MeasureMethod
    scale: Scale
    plans: tuple[Plan, ...] = ()
    elements: tuple[Element, ...] = ()
    rooms: tuple[Room, ...] = ()
    apartments: tuple[Apartment, ...] = ()
    tables: tuple[Table, ...] | None = None
    read: tuple[ReadClass, ...] | None = None  # what it looked for; None: every class and rooms
    model_objects: tuple[ModelObject, ...] | None = None  # the model's objects; None: no model
    notes: tuple[str, ...] = ()


class Measurement(Frozen):
    """Stage 8: one quantity as one method measured it. Two of the same quantity and subject,
    from different methods, become a `Conflict` entry of the drawing model."""

    quantity: ConflictQuantity
    subject: Subject
    value: MeasuredValue


class CountingRule(Frozen):
    """Stage 9: how a quantity is counted, as data. `text` is shown with the answer."""

    id: str
    text: str


class Counted(Frozen):
    """Stage 9: the marks that count for one quantity, and the rule that chose them."""

    rule: CountingRule
    marks: tuple[Mark, ...]


# What a quantity of the takeoff measures, and its unit (stage 10).
Measure = Literal["count", "area", "length", "volume", "text"]
QuantityUnit = Literal["count", "m", "m2", "m3"]


class QuantityConflict(Frozen):
    """Stage 10: the drawing's conflict entry (stage 8) about one quantity of the takeoff, in
    that quantity's unit: every method's value, and the rule that picked one (None: no rule
    decides). `derived`: how the values were carried over from another entry, when they were."""

    values: tuple[MeasuredValue, ...] = Field(min_length=2)
    resolution: Resolution | None
    note: str | None = None
    derived: str | None = None


class Quantity(Frozen):
    """Stage 10: one precomputed answer of the takeoff, with its proof."""

    key: str  # app/core/pipeline/takeoff.py quantity_key(); a plain count is a key of COUNT_KEYS
    value: int | float
    unit: QuantityUnit
    marks: tuple[Mark, ...]
    rule: str  # the id of the counting rule
    estimate: str | None = None  # what an estimated value rests on, in words; None: as read
    conflict: QuantityConflict | None = None  # two methods measured it; `value` is the resolved one


class SheetReport(Frozen):
    """What the stages did to one sheet. `trace` has one readable line per stage."""

    file: str
    sha256: str
    kind: FileKind
    group: str
    route: Route
    source: str
    takeoff: dict[str, int | float]
    trace: tuple[str, ...]


class IngestReport(Frozen):
    sheets: tuple[SheetReport, ...]
    set_aside: tuple[SetAside, ...]
